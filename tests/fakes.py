"""In-memory fakes for testing above the SessionBackend seam."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, TextIO

from matlab_shell.backend import ExecutionHandle, MatlabSession
from matlab_shell.discovery import MatlabInstallation
from matlab_shell.errors import MatlabExecutionError


@dataclass
class EvalScriptResponse:
    """Scripted response for a fake MATLAB evaluation."""

    stdout: str = ""
    stderr: str = ""
    error: Exception | None = None


class FakeExecutionHandle:
    """In-memory ExecutionHandle fake supporting multi-poll and Ctrl+C tests."""

    def __init__(
        self,
        outcome: Any = None,
        error: Exception | None = None,
        *,
        on_done: Callable[[int], bool] | None = None,
    ) -> None:
        self._outcome = outcome
        self._error = error
        self._on_done = on_done
        self._poll_count = 0
        self.cancelled = False

    def done(self) -> bool:
        self._poll_count += 1
        if self._on_done is not None:
            return self._on_done(self._poll_count)
        return True

    def cancel(self) -> bool:
        self.cancelled = True
        return True

    def result(self) -> Any:
        if self._error is not None:
            raise self._error
        return self._outcome


class FakeMatlabSession:
    """In-memory MatlabSession fake recording all interactions."""

    def __init__(
        self,
        *,
        installation: MatlabInstallation,
        is_shared: bool = False,
        session_name: str | None = None,
        initial_cwd: str = "",
        handler: Callable[[str, TextIO, TextIO], None] | None = None,
        async_handler: Callable[[str, TextIO, TextIO], ExecutionHandle] | None = None,
    ) -> None:
        self._installation = installation
        self._is_shared = is_shared
        self._session_name = session_name
        self._handler = handler
        self._async_handler = async_handler
        self.cwd = initial_cwd
        self.cwd_history: list[str] = []
        self.eval_history: list[str] = []
        self.handles: list[ExecutionHandle] = []
        self.closed = False

    @property
    def installation(self) -> MatlabInstallation:
        return self._installation

    @property
    def is_shared(self) -> bool:
        return self._is_shared

    @property
    def session_name(self) -> str | None:
        return self._session_name

    def cd(self, path: str) -> str:
        self.cwd = path
        self.cwd_history.append(path)
        return path

    def pwd(self) -> str:
        return self.cwd

    def eval(self, code: str, *, stdout: TextIO, stderr: TextIO) -> None:
        self.eval_history.append(code)
        if self._handler is not None:
            self._handler(code, stdout, stderr)

    def eval_async(self, code: str, *, stdout: TextIO, stderr: TextIO) -> ExecutionHandle:
        if self._async_handler is not None:
            self.eval_history.append(code)
            handle = self._async_handler(code, stdout, stderr)
            self.handles.append(handle)
            return handle
        try:
            self.eval(code, stdout=stdout, stderr=stderr)
            handle: ExecutionHandle = FakeExecutionHandle()
        except Exception as exc:
            handle = FakeExecutionHandle(error=exc)
        self.handles.append(handle)
        return handle

    def close(self) -> None:
        self.closed = True


@dataclass
class StartManagedCall:
    """Recorded call to SessionBackend.start_managed."""

    installation: MatlabInstallation
    no_figure: bool


class FakeSessionBackend:
    """Configurable in-memory SessionBackend for end-to-end tests."""

    def __init__(
        self,
        *,
        responses: dict[str, EvalScriptResponse] | None = None,
        default_handler: Callable[[str, TextIO, TextIO], None] | None = None,
        async_handler: Callable[[str, TextIO, TextIO], ExecutionHandle] | None = None,
        shared_sessions: tuple[str, ...] = (),
        shared_initial_cwd: str = "",
        start_error: Exception | None = None,
    ) -> None:
        self.responses = responses or {}
        self.default_handler = default_handler
        self.async_handler = async_handler
        self.shared_sessions = shared_sessions
        self.shared_initial_cwd = shared_initial_cwd
        self.start_error = start_error
        self.start_calls: list[StartManagedCall] = []
        self.sessions: list[FakeMatlabSession] = []

    def _handle_eval(self, code: str, stdout: TextIO, stderr: TextIO) -> None:
        if code in self.responses:
            resp = self.responses[code]
            if resp.stdout:
                stdout.write(resp.stdout)
                stdout.flush()
            if resp.stderr:
                stderr.write(resp.stderr)
                stderr.flush()
            if resp.error is not None:
                raise resp.error
            return
        if self.default_handler is not None:
            self.default_handler(code, stdout, stderr)
            return
        if "error(" in code:
            raise MatlabExecutionError("Simulated MATLAB execution error")

    def start_managed(
        self,
        installation: MatlabInstallation,
        *,
        no_figure: bool = False,
    ) -> MatlabSession:
        self.start_calls.append(StartManagedCall(installation=installation, no_figure=no_figure))
        if self.start_error is not None:
            raise self.start_error
        session = FakeMatlabSession(
            installation=installation,
            is_shared=False,
            handler=self._handle_eval,
            async_handler=self.async_handler,
        )
        self.sessions.append(session)
        return session

    def find_shared(self, installation: MatlabInstallation) -> tuple[str, ...]:
        return self.shared_sessions

    def attach_shared(
        self,
        installation: MatlabInstallation,
        name: str | None = None,
    ) -> MatlabSession:
        session = FakeMatlabSession(
            installation=installation,
            is_shared=True,
            session_name=name or (self.shared_sessions[0] if self.shared_sessions else None),
            initial_cwd=self.shared_initial_cwd,
            handler=self._handle_eval,
            async_handler=self.async_handler,
        )
        self.sessions.append(session)
        return session


class ScriptedPromptDriver:
    """Fake PromptDriver yielding scripted strings or exceptions (e.g. KeyboardInterrupt)."""

    def __init__(self, steps: Iterable[str | BaseException]) -> None:
        self._steps = iter(steps)
        self.prompts: list[str] = []

    def prompt(self, message: str) -> str:
        self.prompts.append(message)
        try:
            nxt = next(self._steps)
        except StopIteration as exc:
            raise EOFError from exc
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt
