"""Tests for Shared Session attachment and Meta-Commands."""

from __future__ import annotations

import io
from pathlib import Path
from typing import TextIO

from matlab_shell.cli import run_cli
from matlab_shell.meta import SHARE_ENGINE_HINT
from tests.fakes import FakeSessionBackend, ScriptedPromptDriver
from tests.test_discovery import make_fake_matlab_root


def test_attach_with_no_shared_sessions_errors_cleanly_without_starting_managed(
    tmp_path: Path,
) -> None:
    matlab_root = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")
    backend = FakeSessionBackend(shared_sessions=())
    out = io.StringIO()
    err = io.StringIO()

    code = run_cli(
        ["--attach"],
        backend=backend,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=out,
        stderr=err,
        prompt_driver=ScriptedPromptDriver([]),
        history_path=tmp_path / "history.txt",
        config_path=tmp_path / "missing_config.toml",
    )

    assert code == 1
    assert SHARE_ENGINE_HINT in err.getvalue()
    assert backend.start_calls == []
    assert backend.sessions == []


def test_attach_shared_session_preserves_cwd_unless_cd_passed_and_detaches(
    tmp_path: Path,
) -> None:
    matlab_root = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")
    backend = FakeSessionBackend(shared_sessions=("MATLAB_1234",))
    out = io.StringIO()
    err = io.StringIO()

    # Default --attach leaves CWD untouched
    code = run_cli(
        ["--attach"],
        backend=backend,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=out,
        stderr=err,
        prompt_driver=ScriptedPromptDriver(["exit"]),
        history_path=tmp_path / "history.txt",
        config_path=tmp_path / "missing_config.toml",
    )
    assert code == 0
    assert backend.sessions[0].is_shared is True
    assert backend.sessions[0].session_name == "MATLAB_1234"
    assert backend.sessions[0].cwd_history == []
    assert backend.sessions[0].closed is True
    assert "Detached from Shared Session (MATLAB_1234)." in err.getvalue()

    # With --cd, CWD is synced
    backend2 = FakeSessionBackend(shared_sessions=("MATLAB_1234", "MySession"))
    out2 = io.StringIO()
    err2 = io.StringIO()
    code2 = run_cli(
        ["--attach", "MySession", "--cd"],
        backend=backend2,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=out2,
        stderr=err2,
        prompt_driver=ScriptedPromptDriver([".exit"]),
        history_path=tmp_path / "history2.txt",
        config_path=tmp_path / "missing_config.toml",
    )
    assert code2 == 0
    assert backend2.sessions[0].session_name == "MySession"
    assert backend2.sessions[0].cwd_history == [str(tmp_path)]

    # Interactive selection when multiple shared sessions exist
    backend3 = FakeSessionBackend(shared_sessions=("S1", "S2"))
    driver3 = ScriptedPromptDriver(["2", ".exit"])
    code3 = run_cli(
        ["--attach"],
        backend=backend3,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        prompt_driver=driver3,
        history_path=tmp_path / "history3.txt",
        config_path=tmp_path / "missing_config.toml",
    )
    assert code3 == 0
    assert backend3.sessions[0].session_name == "S2"


def test_meta_commands_and_decimal_number_distinction(tmp_path: Path) -> None:
    matlab_root = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")
    has_vars = False

    def handler(code: str, stdout: TextIO, _stderr: TextIO) -> None:
        nonlocal has_vars
        if code == "x = 1;":
            has_vars = True
        elif code == "whos":
            if has_vars:
                stdout.write("  Name      Size            Bytes  Class     Attributes\n  x         1x1                 8  double\n")
        elif code == ".5 + 1":
            stdout.write("    1.5000\n")

    backend = FakeSessionBackend(
        default_handler=handler,
        shared_sessions=("ExternalMATLAB",),
    )
    cleared = []
    driver = ScriptedPromptDriver(
        [
            ".help",
            ".vars",       # initially empty
            "x = 1;",
            ".vars",       # populated
            ".info",
            ".sessions",
            ".clear",
            ".unknown",
            ".5 + 1",      # numeric expression, NOT a Meta-Command
            ".attach ExternalMATLAB",
            ".info",       # now shows Shared Session
            ".exit",
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
        config_path=tmp_path / "missing_config.toml",
        clear_screen=lambda: cleared.append(True),
    )

    assert code == 0
    out_text = out.getvalue()
    err_text = err.getvalue()

    assert "Meta-Commands:" in out_text
    assert "(Workspace is empty)" in out_text
    assert "double" in out_text
    assert "Managed Session" in out_text
    assert "Available Shared Sessions:" in out_text
    assert "ExternalMATLAB" in out_text
    assert "1.5000" in out_text
    assert "Shared Session (ExternalMATLAB)" in out_text
    assert cleared == [True]
    assert "Unknown meta-command '.unknown'" in err_text
    assert ".unknown" not in backend.sessions[0].eval_history
    assert backend.sessions[0].closed is True
    assert backend.sessions[1].is_shared is True
    assert backend.sessions[1].closed is True
