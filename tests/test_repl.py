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
    assert contains_keyboard_call("x = 1; keyboard") is True
    assert contains_keyboard_call("a'; keyboard") is True
    assert contains_keyboard_call("disp('keyboard')") is False
    assert contains_keyboard_call("% keyboard") is False
    assert contains_keyboard_call("%{\nkeyboard\n%}") is False
    assert contains_keyboard_call("s.keyboard = 1") is False
    assert contains_keyboard_call("s . keyboard = 1") is False


def test_clc_intercept_cd_sync_and_ctrl_c_before_handle(tmp_path: Path) -> None:
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

    from matlab_shell.completer import MatlabCompleter
    from matlab_shell.meta import CLEAR_SCREEN_SEQUENCE
    from matlab_shell.repl import run_repl

    matlab_root = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")
    subdir = tmp_path / "sub_pkg"
    subdir.mkdir()
    (subdir / "inner_fn.m").write_text("disp(1);\n", encoding="utf-8")

    backend: FakeSessionBackend

    def handler(code: str, stdout: TextIO, _stderr: TextIO) -> None:
        if code.strip() == "cd sub_pkg":
            backend.sessions[-1].cwd = str(subdir)

    backend = FakeSessionBackend(default_handler=handler)
    cleared: list[bool] = []
    driver = ScriptedPromptDriver(["clc", "clc;", "cd sub_pkg", ".info", ".exit"])
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
        config_path=tmp_path / "missing_config.toml",
        clear_screen=lambda: cleared.append(True),
    )
    assert code == 0
    assert cleared == [True, True]
    assert "clc" not in backend.sessions[0].eval_history
    assert "clc;" not in backend.sessions[0].eval_history
    assert f"Session CWD:   {subdir}" in out.getvalue()

    # Without custom clear_screen, clc writes CLEAR_SCREEN_SEQUENCE directly
    out_seq = io.StringIO()
    err_seq = io.StringIO()
    backend_seq = FakeSessionBackend()
    code_seq = run_cli(
        [],
        backend=backend_seq,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=out_seq,
        stderr=err_seq,
        prompt_driver=ScriptedPromptDriver(["clc", ".exit"]),
        history_path=tmp_path / "history_seq.txt",
        config_path=tmp_path / "missing_config.toml",
    )
    assert code_seq == 0
    assert CLEAR_SCREEN_SEQUENCE in out_seq.getvalue()

    # Ctrl+C raised inside eval_async (before handle returned) must not raise UnboundLocalError
    def raise_before_handle(_code: str, _stdout: TextIO, _stderr: TextIO) -> FakeExecutionHandle:
        raise KeyboardInterrupt

    backend_int = FakeSessionBackend(async_handler=raise_before_handle)
    err_int = io.StringIO()
    code_int = run_cli(
        [],
        backend=backend_int,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=io.StringIO(),
        stderr=err_int,
        prompt_driver=ScriptedPromptDriver(["long_task", ".exit"]),
        history_path=tmp_path / "history_int.txt",
        config_path=tmp_path / "missing_config.toml",
    )
    assert code_int == 0
    assert "Execution cancelled" in err_int.getvalue()

    # Verify PromptToolkitDriver completer sees updated Session CWD after cd
    from matlab_shell.discovery import MatlabInstallation
    from matlab_shell.repl import PromptToolkitDriver

    captured_completer: list[MatlabCompleter] = []

    class CapturingDriver:
        def __init__(self) -> None:
            self._steps = iter(["cd sub_pkg", "exit"])

        def prompt(self, _msg: str) -> str:
            step = next(self._steps)
            if step == "exit":
                items = [
                    c.text
                    for c in captured_completer[0].get_completions(
                        Document("inner_"),
                        CompleteEvent(completion_requested=True),
                    )
                ]
                assert "inner_fn" in items
            return step

    # Build a completer directly mirroring run_repl wiring and test via run_repl
    _ = PromptToolkitDriver
    session_backend = FakeSessionBackend(
        default_handler=lambda code, _o, _e: setattr(
            session_backend.sessions[-1], "cwd", str(subdir)
        )
        if code == "cd sub_pkg"
        else None
    )
    inst = MatlabInstallation(root=matlab_root, release="R2026a", version="26.1", source="env")

    # Hook MatlabCompleter via monkeypatch-free inspection: check run_repl uses live cwd
    from unittest.mock import patch

    orig_completer_cls = MatlabCompleter

    def spy_completer(*, get_workspace_vars, get_cwd, meta_commands=()):  # type: ignore[no-untyped-def]
        comp = orig_completer_cls(
            get_workspace_vars=get_workspace_vars,
            get_cwd=get_cwd,
        )
        captured_completer.append(comp)
        return comp

    with patch("matlab_shell.repl.MatlabCompleter", side_effect=spy_completer):
        rc = run_repl(
            backend=session_backend,
            installation=inst,
            cwd=tmp_path,
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            history_path=tmp_path / "hist_comp.txt",
            prompt_driver=CapturingDriver(),
        )
    assert rc == 0


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
