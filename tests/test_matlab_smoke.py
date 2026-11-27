"""Opt-in smoke tests against a real local MATLAB R2024a+ installation."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from matlab_shell.cli import run_cli
from matlab_shell.discovery import discover_matlab
from matlab_shell.errors import UNSUPPORTED_INPUT_MESSAGE, UNSUPPORTED_KEYBOARD_MESSAGE
from tests.fakes import ScriptedPromptDriver


@pytest.mark.matlab
def test_real_matlab_oneshot_command(tmp_path: Path) -> None:
    installation = discover_matlab()
    assert installation.root.is_dir()

    out = io.StringIO()
    err = io.StringIO()
    code = run_cli(
        ["-c", "disp(1 + 2)"],
        cwd=tmp_path,
        stdout=out,
        stderr=err,
    )

    assert code == 0
    assert "3" in out.getvalue()
    assert "Starting MATLAB" in err.getvalue()
    assert "Starting MATLAB" not in out.getvalue()


@pytest.mark.matlab
def test_real_matlab_oneshot_script(tmp_path: Path) -> None:
    script = tmp_path / "smoke_demo.m"
    script.write_text("fprintf('hello_from_script\\n');\n", encoding="utf-8")

    out = io.StringIO()
    err = io.StringIO()
    code = run_cli(
        [str(script)],
        cwd=tmp_path,
        stdout=out,
        stderr=err,
    )

    assert code == 0
    assert "hello_from_script" in out.getvalue()


@pytest.mark.matlab
def test_real_matlab_interactive_repl_flow(tmp_path: Path) -> None:
    driver = ScriptedPromptDriver(
        [
            "x = 20;",
            "disp(x + 22)",
            "s = 0;\nfor k = 1:4\n  s = s + k;\nend\ndisp(s)",
            "!echo shell_ok",
            ".vars",
            ".info",
            "keyboard",
            "y = input('n: ')",
            ".exit",
        ]
    )
    out = io.StringIO()
    err = io.StringIO()

    code = run_cli(
        [],
        cwd=tmp_path,
        stdout=out,
        stderr=err,
        prompt_driver=driver,
        history_path=tmp_path / "history.txt",
        config_path=tmp_path / "missing_config.toml",
    )

    assert code == 0
    out_text = out.getvalue()
    assert "42" in out_text
    assert "10" in out_text
    assert "shell_ok" in out_text
    assert "Managed Session" in out_text
    assert "double" in out_text
    err_text = err.getvalue()
    assert UNSUPPORTED_KEYBOARD_MESSAGE in err_text
    assert UNSUPPORTED_INPUT_MESSAGE in err_text
    assert "matlab.internal.engine.input" not in err_text
