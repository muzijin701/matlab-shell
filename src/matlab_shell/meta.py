"""Meta-Command dispatching and Shared Session helpers."""

from __future__ import annotations

import io
import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TextIO

from matlab_shell.backend import MatlabSession, SessionBackend
from matlab_shell.discovery import MatlabInstallation
from matlab_shell.errors import MatlabShellError

_META_CMD_RE = re.compile(r"^\s*\.[A-Za-z]")

SHARE_ENGINE_HINT = (
    "No Shared Session found. Start MATLAB Desktop or run `matlab.engine.shareEngine` "
    "in an open MATLAB Command Window, then retry."
)


@dataclass
class MetaCommandResult:
    """Outcome of executing a Meta-Command inside the interactive prompt."""

    action: Literal["continue", "exit", "switch"]
    new_session: MatlabSession | None = None


def is_meta_command(line: str) -> bool:
    """Return True for `.`-prefixed Meta-Commands (without matching numbers like `.5`)."""
    return _META_CMD_RE.match(line) is not None


def fetch_workspace_var_names(session: MatlabSession) -> list[str]:
    """Read current Workspace variable names without creating temporary variables."""
    out = io.StringIO()
    err = io.StringIO()
    try:
        session.eval("cellfun(@(x) fprintf('%s\\n', x), who);", stdout=out, stderr=err)
    except MatlabShellError:
        return []
    return [line.strip() for line in out.getvalue().splitlines() if line.strip()]


def format_shared_session_unavailable(requested_name: str | None, available: tuple[str, ...]) -> str:
    """Return a clear diagnostic when a Shared Session cannot be attached."""
    if not available:
        return f"Error: {SHARE_ENGINE_HINT}"
    joined = ", ".join(available)
    return (
        f"Error: Shared Session '{requested_name}' was not found. "
        f"Available Shared Sessions: {joined}."
    )


def open_session(
    *,
    backend: SessionBackend,
    installation: MatlabInstallation,
    cwd: Path,
    stderr: TextIO,
    no_figure: bool = False,
    attach_name: str | None = None,
    sync_cwd_on_attach: bool = False,
    choose_shared: Callable[[tuple[str, ...]], str] | None = None,
) -> MatlabSession:
    """Open either a Managed Session or attach to an existing Shared Session."""
    if attach_name is None:
        release_label = f" ({installation.release})" if installation.release else ""
        stderr.write(f"Starting MATLAB{release_label}...\n")
        stderr.flush()
        session = backend.start_managed(installation, no_figure=no_figure)
        session.cd(str(cwd))
        return session

    available = backend.find_shared(installation)
    if not available:
        raise MatlabShellError(SHARE_ENGINE_HINT)

    if attach_name:
        if attach_name not in available:
            joined = ", ".join(available)
            raise MatlabShellError(
                f"Shared Session '{attach_name}' was not found. "
                f"Available Shared Sessions: {joined}."
            )
        chosen = attach_name
    elif len(available) > 1 and choose_shared is not None:
        chosen = choose_shared(available)
    else:
        chosen = available[0]

    session = backend.attach_shared(installation, chosen)
    if sync_cwd_on_attach:
        session.cd(str(cwd))
    stderr.write(f"Attached to Shared Session ({session.session_name or chosen}).\n")
    stderr.flush()
    return session


def dispatch_meta_command(
    line: str,
    *,
    session: MatlabSession,
    backend: SessionBackend,
    installation: MatlabInstallation,
    cwd: Path,
    stdout: TextIO,
    stderr: TextIO,
    clear_screen: Callable[[], None] | None = None,
) -> MetaCommandResult:
    """Execute a `.`-prefixed Meta-Command."""
    try:
        parts = shlex.split(line.strip())
    except ValueError:
        parts = line.strip().split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == ".help":
        stdout.write(
            "Meta-Commands:\n"
            "  .help            Show this help message\n"
            "  .sessions        List available Shared Sessions\n"
            "  .attach [name]   Attach to a Shared Session\n"
            "  .vars            Display Workspace variables (whos)\n"
            "  .clear           Clear the terminal screen\n"
            "  .info            Show bound MATLAB path, version, and active Session\n"
            "  .exit            Exit matlab-shell (or detach from Shared Session)\n"
            "Tips: Alt+Enter inserts a newline, !cmd runs a shell command, "
            "Ctrl+C cancels execution, Ctrl+D exits.\n"
        )
        stdout.flush()
        return MetaCommandResult(action="continue")

    if cmd == ".sessions":
        available = backend.find_shared(installation)
        if not available:
            stdout.write(f"{SHARE_ENGINE_HINT}\n")
        else:
            stdout.write("Available Shared Sessions:\n")
            for name in available:
                marker = " (active)" if session.is_shared and session.session_name == name else ""
                stdout.write(f"  - {name}{marker}\n")
        stdout.flush()
        return MetaCommandResult(action="continue")

    if cmd == ".attach":
        available = backend.find_shared(installation)
        target_name = args[0] if args else None
        if not available:
            stderr.write(f"Error: {SHARE_ENGINE_HINT}\n")
            stderr.flush()
            return MetaCommandResult(action="continue")
        if target_name is not None and target_name not in available:
            stderr.write(f"{format_shared_session_unavailable(target_name, available)}\n")
            stderr.flush()
            return MetaCommandResult(action="continue")

        chosen = target_name or available[0]
        try:
            new_session = backend.attach_shared(installation, chosen)
        except MatlabShellError as exc:
            stderr.write(f"Error: {exc}\n")
            stderr.flush()
            return MetaCommandResult(action="continue")

        session.close()
        stderr.write(f"Attached to Shared Session ({new_session.session_name or chosen}).\n")
        stderr.flush()
        return MetaCommandResult(action="switch", new_session=new_session)

    if cmd == ".vars":
        buf = io.StringIO()
        err_buf = io.StringIO()
        try:
            session.eval("whos", stdout=buf, stderr=err_buf)
        except MatlabShellError as exc:
            stderr.write(f"Error: {exc}\n")
            stderr.flush()
            return MetaCommandResult(action="continue")

        content = buf.getvalue()
        if content.strip():
            stdout.write(content)
            if not content.endswith("\n"):
                stdout.write("\n")
        else:
            stdout.write("(Workspace is empty)\n")
        stdout.flush()
        return MetaCommandResult(action="continue")

    if cmd == ".clear":
        if clear_screen is not None:
            clear_screen()
        else:
            stdout.write("\x1b[2J\x1b[H")
            stdout.flush()
        return MetaCommandResult(action="continue")

    if cmd == ".info":
        session_kind = (
            f"Shared Session ({session.session_name})"
            if session.is_shared and session.session_name
            else ("Shared Session" if session.is_shared else "Managed Session")
        )
        stdout.write(
            f"MATLAB Root:   {installation.root}\n"
            f"Release:       {installation.release or 'unknown'}\n"
            f"Version:       {installation.version or 'unknown'}\n"
            f"Discovery:     {installation.source}\n"
            f"Session Type:  {session_kind}\n"
            f"Terminal CWD:  {cwd}\n"
        )
        stdout.flush()
        return MetaCommandResult(action="continue")

    if cmd == ".exit":
        return MetaCommandResult(action="exit")

    stderr.write(f"Error: Unknown meta-command '{cmd}'. Type '.help' for available commands.\n")
    stderr.flush()
    return MetaCommandResult(action="continue")
