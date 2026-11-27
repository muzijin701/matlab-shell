"""Tests for interactive REPL, history, syntax highlighting, interruption, and error mapping."""

from __future__ import annotations

import io
from pathlib import Path
from typing import TextIO

import pytest
from prompt_toolkit.history import FileHistory
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output.defaults import DummyOutput
from pygments.lexers.matlab import MatlabLexer

from matlab_shell.cli import run_cli
from matlab_shell.errors import (
    UNSUPPORTED_INPUT_MESSAGE,
    UNSUPPORTED_KEYBOARD_MESSAGE,
    MatlabExecutionError,
    contains_keyboard_call,
)
from matlab_shell.paths import get_history_path
from matlab_shell.repl import PromptToolkitDriver
from tests.fakes import FakeExecutionHandle, FakeSessionBackend, ScriptedPromptDriver
from tests.test_discovery import make_fake_matlab_root


def _make_stateful_workspace_backend() -> FakeSessionBackend:
    workspace: dict[str, int] = {}

    def handler(code: str, stdout: TextIO, _stderr: TextIO) -> None:
        stripped = code.strip().rstrip(";")
        if stripped == "a = 10":
            workspace["a"] = 10
        elif stripped == "b = a + 5":
            workspace["b"] = workspace["a"] + 5
        elif stripped == "disp(b)":
            stdout.write(f"    {workspace['b']}\n")
            stdout.flush()
        elif stripped.startswith("run('") and "init_script.m" in stripped:
            workspace["seed"] = 40
        elif stripped == "disp(seed + 2)":
            stdout.write(f"    {workspace['seed'] + 2}\n")
            stdout.flush()
        elif stripped.startswith("!echo "):
            stdout.write(f"{stripped[6:]}\n")
            stdout.flush()

    return FakeSessionBackend(default_handler=handler)


@pytest.mark.parametrize("exit_step", ["exit", "quit", "exit;", EOFError()])
def test_repl_preserves_workspace_and_exits_cleanly(
    tmp_path: Path,
    exit_step: str | BaseException,
) -> None:
    matlab_root = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")
    backend = _make_stateful_workspace_backend()
    driver = ScriptedPromptDriver(["a = 10;", "   ", "b = a + 5;", "disp(b)", exit_step])
    out = io.StringIO()
    err = io.StringIO()

    code = run_cli(
        [],
        backend=backend,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=out,
        stderr=err,
        prompt_driver=driver,
        history_path=tmp_path / "history.txt",
    )

    assert code == 0
    assert out.getvalue() == "    15\n"
    assert "Starting MATLAB (R2026a)" in err.getvalue()
    assert "MATLAB R2026a ready." in err.getvalue()
    assert driver.prompts[0] == ">> "
    assert backend.sessions[0].closed is True


def test_interactive_flag_runs_script_then_enters_repl(tmp_path: Path) -> None:
    matlab_root = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")
    script = tmp_path / "init_script.m"
    script.write_text("seed = 40;\n", encoding="utf-8")

    backend = _make_stateful_workspace_backend()
    driver = ScriptedPromptDriver(["disp(seed + 2)", "exit"])
    out = io.StringIO()
    err = io.StringIO()

    code = run_cli(
        ["-i", str(script)],
        backend=backend,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=out,
        stderr=err,
        prompt_driver=driver,
        history_path=tmp_path / "history.txt",
    )

    assert code == 0
    assert out.getvalue() == "    42\n"
    assert backend.sessions[0].closed is True

    # Even if the initial script errors, -i still enters the REPL
    err_backend = FakeSessionBackend(default_handler=lambda *_args: (_ for _ in ()).throw(MatlabExecutionError("boom")))
    err_driver = ScriptedPromptDriver(["exit"])
    out2 = io.StringIO()
    err2 = io.StringIO()
    code2 = run_cli(
        ["-i", "-c", "boom"],
        backend=err_backend,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=out2,
        stderr=err2,
        prompt_driver=err_driver,
        history_path=tmp_path / "history2.txt",
    )
    assert code2 == 0
    assert "boom" in err2.getvalue()
    assert err_driver.prompts == [">> "]


def test_history_persists_across_sessions_in_plain_text_file(tmp_path: Path) -> None:
    history_file = tmp_path / "nested" / "history.txt"
    with create_pipe_input() as pipe:
        driver1 = PromptToolkitDriver(
            history_path=history_file,
            pt_input=pipe,
            pt_output=DummyOutput(),
        )
        pipe.send_text("x = 123;\r")
        assert driver1.prompt(">> ") == "x = 123;"

    assert history_file.is_file()
    assert "x = 123;" in history_file.read_text(encoding="utf-8")

    # Reload in a brand-new FileHistory / PromptToolkitDriver
    reloaded = FileHistory(str(history_file))
    assert "x = 123;" in list(reloaded.load_history_strings())


def test_prompt_toolkit_driver_configures_matlab_lexer_and_history(tmp_path: Path) -> None:
    history_file = tmp_path / "history.txt"
    with create_pipe_input() as pipe:
        driver = PromptToolkitDriver(
            history_path=history_file,
            pt_input=pipe,
            pt_output=DummyOutput(),
        )
        assert isinstance(driver.session.history, FileHistory)
        assert driver.session.enable_history_search is True
        assert driver.session.lexer is not None
        assert driver.session.lexer.pygments_lexer_cls is MatlabLexer


def test_ctrl_c_idle_clears_buffer_and_active_cancels_execution(tmp_path: Path) -> None:
    matlab_root = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")

    def async_handler(code: str, stdout: TextIO, _stderr: TextIO) -> FakeExecutionHandle:
        if code == "pause(10)":
            def interrupt_on_second_poll(poll_count: int) -> bool:
                if poll_count >= 2:
                    raise KeyboardInterrupt
                return False

            return FakeExecutionHandle(on_done=interrupt_on_second_poll)
        stdout.write("still alive\n")
        stdout.flush()
        return FakeExecutionHandle()

    backend = FakeSessionBackend(async_handler=async_handler)
    driver = ScriptedPromptDriver(
        [
            KeyboardInterrupt(),  # idle Ctrl+C
            "pause(10)",          # active Ctrl+C during execution
            "disp('still alive')",
            "exit",
        ]
    )
    out = io.StringIO()
    err = io.StringIO()

    code = run_cli(
        [],
        backend=backend,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=out,
        stderr=err,
        prompt_driver=driver,
        history_path=tmp_path / "history.txt",
    )

    assert code == 0
    assert out.getvalue() == "still alive\n"
    assert "Execution cancelled" in err.getvalue()
    # Second handle corresponds to "pause(10)"? Wait: idle Ctrl+C didn't create a handle, so index 0 is pause(10)
    assert backend.sessions[0].handles[0].cancelled is True  # type: ignore[attr-defined]
    assert backend.sessions[0].closed is True


def test_unsupported_input_and_keyboard_give_friendly_errors(tmp_path: Path) -> None:
    matlab_root = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")

    def handler(code: str, stdout: TextIO, stderr: TextIO) -> None:
        if code == "x = input('en: ')":
            raise MatlabExecutionError(
                "Error using matlab.internal.engine.input\n"
                "The 'input' command is not supported in MATLAB started by Engine without Desktop."
            )
        if code == "y = input('zh: ')":
            stderr.write("由不带 Desktop 的 Engine 启动的 MATLAB 不支持 'input' 命令。\n")
            raise MatlabExecutionError(
                "File D:\\matlab\\+matlab\\+internal\\+engine\\input.m, line 20"
            )
        stdout.write(f"ran:{code}\n")

    backend = FakeSessionBackend(default_handler=handler)
    driver = ScriptedPromptDriver(
        [
            "x = input('en: ')",
            "y = input('zh: ')",
            "keyboard",
            "disp('keyboard')",
            "% keyboard",
            "exit",
        ]
    )
    out = io.StringIO()
    err = io.StringIO()

    code = run_cli(
        [],
        backend=backend,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=out,
        stderr=err,
        prompt_driver=driver,
        history_path=tmp_path / "history.txt",
    )

    assert code == 0
    assert out.getvalue() == "ran:disp('keyboard')\nran:% keyboard\n"
    err_text = err.getvalue()
    assert err_text.count(UNSUPPORTED_INPUT_MESSAGE) == 2
    assert UNSUPPORTED_KEYBOARD_MESSAGE in err_text
    assert "matlab.internal.engine.input" not in err_text
    assert "keyboard" not in backend.sessions[0].eval_history

    assert contains_keyboard_call("keyboard") is True
    assert contains_keyboard_call("a'; keyboard") is True
    assert contains_keyboard_call("disp('keyboard')") is False
    assert contains_keyboard_call("% keyboard") is False


def test_shell_escape_passthrough(tmp_path: Path) -> None:
    matlab_root = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")
    backend = _make_stateful_workspace_backend()
    driver = ScriptedPromptDriver(["!echo hello_shell", "exit"])
    out = io.StringIO()
    err = io.StringIO()

    code = run_cli(
        [],
        backend=backend,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=out,
        stderr=err,
        prompt_driver=driver,
        history_path=tmp_path / "history.txt",
    )

    assert code == 0
    assert out.getvalue() == "hello_shell\n"
    assert "!echo hello_shell" in backend.sessions[0].eval_history


def test_data_dir_paths_per_platform(tmp_path: Path) -> None:
    win_path = get_history_path(
        env={"LOCALAPPDATA": str(tmp_path / "LocalApp")},
        system="Windows",
        home=tmp_path,
    )
    assert win_path == tmp_path / "LocalApp" / "matlab-shell" / "history.txt"

    mac_path = get_history_path(env={}, system="Darwin", home=tmp_path)
    assert mac_path == tmp_path / "Library" / "Application Support" / "matlab-shell" / "history.txt"

    linux_xdg = get_history_path(
        env={"XDG_DATA_HOME": str(tmp_path / "xdg")},
        system="Linux",
        home=tmp_path,
    )
    assert linux_xdg == tmp_path / "xdg" / "matlab-shell" / "history.txt"

    linux_default = get_history_path(env={}, system="Linux", home=tmp_path)
    assert linux_default == tmp_path / ".local" / "share" / "matlab-shell" / "history.txt"
