"""End-to-end tests for CLI and One-Shot Execution above SessionBackend."""

from __future__ import annotations

import io
from pathlib import Path

from matlab_shell.cli import run_cli
from matlab_shell.errors import MatlabExecutionError
from tests.fakes import EvalScriptResponse, FakeSessionBackend
from tests.test_discovery import make_fake_matlab_root


def test_oneshot_inline_command_streams_cleanly_and_closes_session(tmp_path: Path) -> None:
    matlab_root = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    backend = FakeSessionBackend(
        responses={"disp(1+1)": EvalScriptResponse(stdout="     2\n")}
    )
    out = io.StringIO()
    err = io.StringIO()

    code = run_cli(
        ["-c", "disp(1+1)"],
        backend=backend,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=work_dir,
        stdout=out,
        stderr=err,
    )

    assert code == 0
    assert out.getvalue() == "     2\n"
    assert "Starting MATLAB (R2026a)" in err.getvalue()
    assert "Starting MATLAB" not in out.getvalue()

    assert len(backend.sessions) == 1
    session = backend.sessions[0]
    assert session.cwd_history == [str(work_dir)]
    assert session.eval_history == ["disp(1+1)"]
    assert session.closed is True
    assert backend.start_calls[0].no_figure is False


def test_oneshot_script_execution_handles_quotes_and_relative_path(tmp_path: Path) -> None:
    matlab_root = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")
    work_dir = tmp_path / "bob's work"
    work_dir.mkdir()
    script = work_dir / "demo.m"
    script.write_text("disp('ok');\n", encoding="utf-8")

    expected_stmt = f"run('{str(script.resolve()).replace(chr(39), chr(39) * 2)}')"
    backend = FakeSessionBackend(
        responses={expected_stmt: EvalScriptResponse(stdout="ok\n")}
    )
    out = io.StringIO()
    err = io.StringIO()

    code = run_cli(
        ["demo.m"],
        backend=backend,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=work_dir,
        stdout=out,
        stderr=err,
    )

    assert code == 0
    assert out.getvalue() == "ok\n"
    assert backend.sessions[0].eval_history == [expected_stmt]
    assert backend.sessions[0].closed is True


def test_missing_script_and_conflicting_args_fail_fast_without_starting_session(
    tmp_path: Path,
) -> None:
    matlab_root = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")
    script = tmp_path / "exists.m"
    script.write_text("x = 1;\n", encoding="utf-8")

    backend = FakeSessionBackend()
    out = io.StringIO()
    err = io.StringIO()

    code_missing = run_cli(
        ["nonexistent.m"],
        backend=backend,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=out,
        stderr=err,
    )
    assert code_missing == 2
    assert "not found" in err.getvalue().lower()
    assert backend.start_calls == []

    err = io.StringIO()
    code_conflict = run_cli(
        ["-c", "x=1", str(script)],
        backend=backend,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=out,
        stderr=err,
    )
    assert code_conflict == 2
    assert "both" in err.getvalue().lower()
    assert backend.start_calls == []


def test_execution_error_writes_stderr_closes_session_and_returns_nonzero(
    tmp_path: Path,
) -> None:
    matlab_root = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")
    backend = FakeSessionBackend(
        responses={
            "bad_call": EvalScriptResponse(
                error=MatlabExecutionError("Undefined function 'bad_call'."),
            )
        }
    )
    out = io.StringIO()
    err = io.StringIO()

    code = run_cli(
        ["-c", "bad_call"],
        backend=backend,
        env={"MATLAB_SHELL_ROOT": str(matlab_root)},
        cwd=tmp_path,
        stdout=out,
        stderr=err,
    )

    assert code == 1
    assert out.getvalue() == ""
    assert "Undefined function 'bad_call'" in err.getvalue()
    assert backend.sessions[0].closed is True


def test_no_figure_and_explicit_matlab_root_flags(tmp_path: Path) -> None:
    explicit_root = make_fake_matlab_root(tmp_path, "R2025b", release="R2025b")
    other_root = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")
    backend = FakeSessionBackend()
    out = io.StringIO()
    err = io.StringIO()

    code = run_cli(
        ["--matlab-root", str(explicit_root), "--no-figure", "-c", "x = 1;"],
        backend=backend,
        env={"MATLAB_SHELL_ROOT": str(other_root)},
        cwd=tmp_path,
        stdout=out,
        stderr=err,
    )

    assert code == 0
    assert backend.start_calls[0].installation.root == explicit_root
    assert backend.start_calls[0].no_figure is True
    assert backend.sessions[0].closed is True
