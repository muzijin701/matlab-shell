"""Interactive MATLAB REPL built on prompt_toolkit and SessionBackend."""

from __future__ import annotations

import io
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Protocol, TextIO

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.matlab import MatlabLexer

from matlab_shell.backend import MatlabSession, SessionBackend
from matlab_shell.completer import MatlabCompleter
from matlab_shell.config import EditingMode as ConfigEditingMode
from matlab_shell.discovery import MatlabInstallation
from matlab_shell.errors import (
    UNSUPPORTED_KEYBOARD_MESSAGE,
    MatlabExecutionError,
    MatlabShellError,
    contains_keyboard_call,
    format_execution_error,
)
from matlab_shell.meta import (
    dispatch_meta_command,
    fetch_workspace_var_names,
    is_meta_command,
    open_session,
)
from matlab_shell.multiline import is_complete_statement
from matlab_shell.runner import matlab_run_script_statement


class PromptDriver(Protocol):
    """Input prompt abstraction for the interactive REPL."""

    def prompt(self, message: str) -> str: ...


def build_repl_key_bindings() -> KeyBindings:
    """Create Enter / Alt+Enter key bindings supporting automatic multiline continuation."""
    kb = KeyBindings()

    @kb.add("enter")
    def _on_enter(event: Any) -> None:
        buf = event.current_buffer
        if buf.complete_state and buf.complete_state.current_completion:
            buf.apply_completion(buf.complete_state.current_completion)
            return
        if is_complete_statement(buf.text):
            buf.validate_and_handle()
        else:
            buf.insert_text("\n")

    @kb.add("escape", "enter")
    def _on_alt_enter(event: Any) -> None:
        event.current_buffer.insert_text("\n")

    return kb


class PromptToolkitDriver:
    """prompt_toolkit-backed interactive prompt with history, highlighting, multiline, and completion."""

    def __init__(
        self,
        *,
        history_path: Path,
        editing_mode: ConfigEditingMode = "emacs",
        completer: Completer | None = None,
        pt_input: Any = None,
        pt_output: Any = None,
    ) -> None:
        self.history_path = history_path
        history_path.parent.mkdir(parents=True, exist_ok=True)
        pt_mode = EditingMode.VI if editing_mode == "vi" else EditingMode.EMACS
        kwargs: dict[str, Any] = {
            "history": FileHistory(str(history_path)),
            "lexer": PygmentsLexer(MatlabLexer),
            "enable_history_search": True,
            "multiline": True,
            "prompt_continuation": "... ",
            "editing_mode": pt_mode,
            "completer": completer,
            "complete_while_typing": False,
            "key_bindings": build_repl_key_bindings(),
        }
        if pt_input is not None:
            kwargs["input"] = pt_input
        if pt_output is not None:
            kwargs["output"] = pt_output
        self.session: PromptSession[str] = PromptSession(**kwargs)

    def prompt(self, message: str) -> str:
        return self.session.prompt(message)


def is_exit_command(line: str) -> bool:
    """Return True for `exit` / `quit` (with optional trailing semicolon)."""
    return line.strip().rstrip(";").strip().lower() in {"exit", "quit"}


def execute_statement(
    session: MatlabSession,
    code: str,
    *,
    stdout: TextIO,
    stderr: TextIO,
    poll_interval: float = 0.02,
) -> bool:
    """Execute one MATLAB statement asynchronously, supporting Ctrl+C cancellation."""
    if contains_keyboard_call(code):
        stderr.write(f"{UNSUPPORTED_KEYBOARD_MESSAGE}\n")
        stderr.flush()
        return False

    err_buf = io.StringIO()
    try:
        handle = session.eval_async(code, stdout=stdout, stderr=err_buf)
        while not handle.done():
            time.sleep(poll_interval)
        handle.result()
    except KeyboardInterrupt:
        cancelled = handle.cancel()  # type: ignore[possibly-undefined]
        if cancelled:
            stderr.write("^C — Execution cancelled.\n")
        else:
            stderr.write("^C — Cancellation requested (waiting for engine to return).\n")
        stderr.flush()
        return False
    except MatlabExecutionError as exc:
        stderr.write(f"{format_execution_error(exc, err_buf.getvalue())}\n")
        stderr.flush()
        return False

    buffered_err = err_buf.getvalue()
    if buffered_err:
        stderr.write(buffered_err)
        if not buffered_err.endswith("\n"):
            stderr.write("\n")
        stderr.flush()
    return True


def _select_shared_session_interactively(
    available: tuple[str, ...],
    *,
    driver: PromptDriver,
    stderr: TextIO,
) -> str:
    stderr.write("Multiple Shared Sessions found:\n")
    for idx, name in enumerate(available, start=1):
        stderr.write(f"  [{idx}] {name}\n")
    stderr.flush()

    while True:
        try:
            choice = driver.prompt(f"Select session [1-{len(available)}, default 1]: ").strip()
        except (EOFError, KeyboardInterrupt) as exc:
            raise MatlabShellError("Shared Session selection cancelled.") from exc
        if not choice:
            return available[0]
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(available):
                return available[idx - 1]
        if choice in available:
            return choice
        stderr.write(f"Invalid selection '{choice}'. Enter a number 1-{len(available)} or session name.\n")
        stderr.flush()


def run_repl(
    *,
    backend: SessionBackend,
    installation: MatlabInstallation,
    cwd: Path,
    stdout: TextIO,
    stderr: TextIO,
    history_path: Path,
    prompt_driver: PromptDriver | None = None,
    initial_command: str | None = None,
    initial_script: Path | None = None,
    no_figure: bool = False,
    attach_name: str | None = None,
    sync_cwd_on_attach: bool = False,
    editing_mode: ConfigEditingMode = "emacs",
    clear_screen: Callable[[], None] | None = None,
    poll_interval: float = 0.02,
) -> int:
    """Open a Managed or Shared Session, run optional startup code, and enter `>>` REPL."""
    workspace_vars: list[str] = []
    completer = MatlabCompleter(
        get_workspace_vars=lambda: workspace_vars,
        get_cwd=lambda: cwd,
    )
    driver = (
        prompt_driver
        if prompt_driver is not None
        else PromptToolkitDriver(
            history_path=history_path,
            editing_mode=editing_mode,
            completer=completer,
        )
    )

    def choose_shared(available: tuple[str, ...]) -> str:
        return _select_shared_session_interactively(available, driver=driver, stderr=stderr)

    session = open_session(
        backend=backend,
        installation=installation,
        cwd=cwd,
        stderr=stderr,
        no_figure=no_figure,
        attach_name=attach_name,
        sync_cwd_on_attach=sync_cwd_on_attach,
        choose_shared=choose_shared,
    )
    try:
        if initial_script is not None:
            execute_statement(
                session,
                matlab_run_script_statement(initial_script),
                stdout=stdout,
                stderr=stderr,
                poll_interval=poll_interval,
            )
        elif initial_command is not None:
            execute_statement(
                session,
                initial_command,
                stdout=stdout,
                stderr=stderr,
                poll_interval=poll_interval,
            )

        workspace_vars = fetch_workspace_var_names(session)

        ready_release = f" {installation.release}" if installation.release else ""
        exit_verb = "detach" if session.is_shared else "quit"
        stderr.write(
            f"MATLAB{ready_release} ready. Type '.help' for commands, 'exit' or Ctrl+D to {exit_verb}.\n"
        )
        stderr.flush()

        while True:
            try:
                line = driver.prompt(">> ")
            except KeyboardInterrupt:
                continue
            except EOFError:
                stderr.write("\n")
                stderr.flush()
                break

            if not line.strip():
                continue

            if is_meta_command(line):
                outcome = dispatch_meta_command(
                    line,
                    session=session,
                    backend=backend,
                    installation=installation,
                    cwd=cwd,
                    stdout=stdout,
                    stderr=stderr,
                    clear_screen=clear_screen,
                )
                if outcome.action == "exit":
                    break
                if outcome.action == "switch" and outcome.new_session is not None:
                    session = outcome.new_session
                    workspace_vars = fetch_workspace_var_names(session)
                elif line.strip().lower().startswith(".vars"):
                    workspace_vars = fetch_workspace_var_names(session)
                continue

            if is_exit_command(line):
                break

            if execute_statement(
                session,
                line,
                stdout=stdout,
                stderr=stderr,
                poll_interval=poll_interval,
            ):
                workspace_vars = fetch_workspace_var_names(session)
        return 0
    finally:
        was_shared = session.is_shared
        shared_name = session.session_name
        session.close()
        if was_shared:
            label = f" ({shared_name})" if shared_name else ""
            stderr.write(f"Detached from Shared Session{label}.\n")
            stderr.flush()
