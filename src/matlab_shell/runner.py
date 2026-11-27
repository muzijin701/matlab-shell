"""Execution runner for One-Shot Execution."""

from __future__ import annotations

import io
from pathlib import Path
from typing import TextIO

from matlab_shell.backend import SessionBackend
from matlab_shell.discovery import MatlabInstallation
from matlab_shell.errors import (
    UNSUPPORTED_KEYBOARD_MESSAGE,
    MatlabExecutionError,
    contains_keyboard_call,
    format_execution_error,
)
from matlab_shell.meta import open_session


def matlab_run_script_statement(script_path: Path) -> str:
    """Build a MATLAB run(...) statement safely escaping single quotes."""
    escaped = str(script_path.resolve()).replace("'", "''")
    return f"run('{escaped}')"


def run_oneshot(
    *,
    backend: SessionBackend,
    installation: MatlabInstallation,
    cwd: Path,
    stdout: TextIO,
    stderr: TextIO,
    command: str | None = None,
    script: Path | None = None,
    no_figure: bool = False,
    attach_name: str | None = None,
    sync_cwd_on_attach: bool = False,
) -> int:
    """Run a single command or script in a Managed or Shared Session and exit cleanly."""
    if (command is None) == (script is None):
        raise ValueError("Provide exactly one of command or script")

    statement = command if command is not None else matlab_run_script_statement(script)  # type: ignore[arg-type]
    if contains_keyboard_call(statement):
        stderr.write(f"{UNSUPPORTED_KEYBOARD_MESSAGE}\n")
        stderr.flush()
        return 1

    session = open_session(
        backend=backend,
        installation=installation,
        cwd=cwd,
        stderr=stderr,
        no_figure=no_figure,
        attach_name=attach_name,
        sync_cwd_on_attach=sync_cwd_on_attach,
    )
    err_buf = io.StringIO()

    try:
        session.eval(statement, stdout=stdout, stderr=err_buf)
        buffered_err = err_buf.getvalue()
        if buffered_err:
            stderr.write(buffered_err)
            if not buffered_err.endswith("\n"):
                stderr.write("\n")
            stderr.flush()
        return 0
    except MatlabExecutionError as exc:
        stderr.write(f"{format_execution_error(exc, err_buf.getvalue())}\n")
        stderr.flush()
        return 1
    finally:
        was_shared = session.is_shared
        shared_name = session.session_name
        session.close()
        if was_shared:
            label = f" ({shared_name})" if shared_name else ""
            stderr.write(f"Detached from Shared Session{label}.\n")
            stderr.flush()
