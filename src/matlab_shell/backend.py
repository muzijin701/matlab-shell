"""SessionBackend seam and dynamic local MATLAB engine loader."""

from __future__ import annotations

import importlib
import io
import os
import platform
import sys
from pathlib import Path
from typing import Any, Protocol, TextIO

from matlab_shell.discovery import MatlabInstallation, get_platform_arch
from matlab_shell.errors import MatlabExecutionError, MatlabLoadError

_DLL_DIRECTORY_HANDLES: list[Any] = []


class ExecutionHandle(Protocol):
    """Handle for an asynchronous MATLAB evaluation."""

    def done(self) -> bool: ...

    def cancel(self) -> bool: ...

    def result(self) -> Any: ...


class MatlabSession(Protocol):
    """Active MATLAB Session interface."""

    @property
    def installation(self) -> MatlabInstallation: ...

    @property
    def is_shared(self) -> bool: ...

    @property
    def session_name(self) -> str | None: ...

    def cd(self, path: str) -> str: ...

    def eval(self, code: str, *, stdout: TextIO, stderr: TextIO) -> None: ...

    def eval_async(self, code: str, *, stdout: TextIO, stderr: TextIO) -> ExecutionHandle: ...

    def close(self) -> None: ...


class SessionBackend(Protocol):
    """Primary testing seam encapsulating MATLAB Engine operations."""

    def start_managed(
        self,
        installation: MatlabInstallation,
        *,
        no_figure: bool = False,
    ) -> MatlabSession: ...

    def find_shared(self, installation: MatlabInstallation) -> tuple[str, ...]: ...

    def attach_shared(
        self,
        installation: MatlabInstallation,
        name: str | None = None,
    ) -> MatlabSession: ...


class _FlushingStream(io.StringIO):
    """io.StringIO subclass that forwards MATLAB writes immediately to a TextIO target."""

    def __init__(self, target: TextIO) -> None:
        super().__init__()
        self._target = target

    def write(self, data: str) -> int:
        written = self._target.write(data)
        self._target.flush()
        return written

    def flush(self) -> None:
        self._target.flush()

    def drain_buffered(self) -> None:
        """Flush any text written directly into the base StringIO C buffer."""
        buffered = super().getvalue()
        if buffered:
            self._target.write(buffered)
            self._target.flush()
            self.seek(0)
            self.truncate(0)


class _FutureExecutionHandle:
    """Adapter around matlab.engine FutureResult."""

    def __init__(
        self,
        future: Any,
        out_stream: _FlushingStream,
        err_stream: _FlushingStream,
    ) -> None:
        self._future = future
        self._out_stream = out_stream
        self._err_stream = err_stream

    def done(self) -> bool:
        return bool(self._future.done())

    def cancel(self) -> bool:
        return bool(self._future.cancel())

    def result(self) -> Any:
        try:
            return self._future.result()
        except Exception as exc:
            raise MatlabExecutionError(str(exc)) from exc
        finally:
            self._out_stream.drain_buffered()
            self._err_stream.drain_buffered()


def _prepend_sys_path(path: Path) -> None:
    path_str = str(path)
    if path.is_dir() and path_str not in sys.path:
        sys.path.insert(0, path_str)


def _register_windows_dll_dirs(dirs: list[Path]) -> None:
    if platform.system() != "Windows":
        return
    current_path = os.environ.get("PATH", "")
    path_parts = current_path.split(os.pathsep) if current_path else []
    for directory in dirs:
        if not directory.is_dir():
            continue
        dir_str = str(directory)
        if dir_str not in path_parts:
            path_parts.insert(0, dir_str)
        if hasattr(os, "add_dll_directory"):
            _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(dir_str))
    os.environ["PATH"] = os.pathsep.join(path_parts)


def load_matlab_engine_module(installation: MatlabInstallation) -> Any:
    """Dynamically load `matlab.engine` from a local MATLAB installation."""
    root = installation.root
    arch = get_platform_arch()
    dist_dir = root / "extern" / "engines" / "python" / "dist"
    engine_arch_dir = dist_dir / "matlab" / "engine" / arch
    extern_bin_dir = root / "extern" / "bin" / arch
    bin_dir = root / "bin" / arch

    _prepend_sys_path(dist_dir)
    _prepend_sys_path(engine_arch_dir)
    _prepend_sys_path(extern_bin_dir)
    _register_windows_dll_dirs([bin_dir, extern_bin_dir])

    try:
        return importlib.import_module("matlab.engine")
    except Exception as exc:
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        raise MatlabLoadError(
            f"Failed to load MATLAB Python engine from {root} (Python {py_ver}): {exc}"
        ) from exc


class RealMatlabSession:
    """Live MATLAB Session backed by a `matlab.engine.MatlabEngine` instance."""

    def __init__(
        self,
        engine: Any,
        *,
        installation: MatlabInstallation,
        is_shared: bool,
        session_name: str | None = None,
    ) -> None:
        self._eng = engine
        self._installation = installation
        self._is_shared = is_shared
        self._session_name = session_name
        self._closed = False

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
        try:
            return str(self._eng.cd(str(path), nargout=1))
        except Exception as exc:
            raise MatlabExecutionError(str(exc)) from exc

    def eval(self, code: str, *, stdout: TextIO, stderr: TextIO) -> None:
        out_w = _FlushingStream(stdout)
        err_w = _FlushingStream(stderr)
        try:
            self._eng.eval(code, nargout=0, stdout=out_w, stderr=err_w)
        except Exception as exc:
            raise MatlabExecutionError(str(exc)) from exc
        finally:
            out_w.drain_buffered()
            err_w.drain_buffered()

    def eval_async(self, code: str, *, stdout: TextIO, stderr: TextIO) -> ExecutionHandle:
        out_w = _FlushingStream(stdout)
        err_w = _FlushingStream(stderr)
        try:
            future = self._eng.eval(code, nargout=0, background=True, stdout=out_w, stderr=err_w)
            return _FutureExecutionHandle(future, out_w, err_w)
        except Exception as exc:
            raise MatlabExecutionError(str(exc)) from exc

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._is_shared:
                self._eng.exit()
            else:
                self._eng.quit()
        except Exception:
            pass


class RealSessionBackend:
    """Production SessionBackend using dynamically loaded `matlab.engine`."""

    def start_managed(
        self,
        installation: MatlabInstallation,
        *,
        no_figure: bool = False,
    ) -> MatlabSession:
        engine_mod = load_matlab_engine_module(installation)
        option = "-nodesktop -noFigureWindows" if no_figure else "-nodesktop"
        try:
            eng = engine_mod.start_matlab(option)
        except Exception as exc:
            raise MatlabLoadError(f"Failed to start MATLAB session from {installation.root}: {exc}") from exc
        return RealMatlabSession(
            eng,
            installation=installation,
            is_shared=False,
            session_name=None,
        )

    def find_shared(self, installation: MatlabInstallation) -> tuple[str, ...]:
        engine_mod = load_matlab_engine_module(installation)
        return tuple(engine_mod.find_matlab())

    def attach_shared(
        self,
        installation: MatlabInstallation,
        name: str | None = None,
    ) -> MatlabSession:
        engine_mod = load_matlab_engine_module(installation)
        try:
            eng = engine_mod.connect_matlab() if name is None else engine_mod.connect_matlab(name)
        except Exception as exc:
            raise MatlabLoadError(f"Failed to attach to shared MATLAB session: {exc}") from exc
        return RealMatlabSession(
            eng,
            installation=installation,
            is_shared=True,
            session_name=name,
        )
