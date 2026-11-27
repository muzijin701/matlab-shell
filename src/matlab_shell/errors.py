"""Domain error types and friendly MATLAB engine error helpers."""

from __future__ import annotations

import re

UNSUPPORTED_INPUT_MESSAGE = (
    "Error: Interactive `input()` is not supported in matlab-shell because the MATLAB Engine "
    "runs without a console stdin stream. Set variables in the Workspace or pass arguments to "
    "functions instead."
)

UNSUPPORTED_KEYBOARD_MESSAGE = (
    "Error: Interactive `keyboard` debugging is not supported in matlab-shell because the MATLAB "
    "Engine runs without a console stdin stream (calling it would block waiting for input)."
)

_KEYBOARD_RE = re.compile(r"\bkeyboard\b")
_UNSUPPORTED_INPUT_MARKERS = (
    "matlab.internal.engine.input",
    "'input' command is not supported",
    "不支持 'input' 命令",
    "cannot call 'input'",
)


class MatlabShellError(Exception):
    """Base error for matlab-shell operations."""


class MatlabDiscoveryError(MatlabShellError):
    """Raised when no valid, supported local MATLAB installation is found."""


class MatlabLoadError(MatlabShellError):
    """Raised when dynamically loading the local MATLAB Python engine fails."""


class MatlabExecutionError(MatlabShellError):
    """Raised when evaluating MATLAB code in a Session fails."""


class MatlabConfigError(MatlabShellError):
    """Raised when user configuration (`config.toml`) is malformed or invalid."""


def strip_matlab_comments_and_strings(code: str) -> str:
    """Strip MATLAB comments and string literals for lightweight token scanning."""
    out: list[str] = []
    i = 0
    n = len(code)
    while i < n:
        ch = code[i]
        if ch == "%":
            while i < n and code[i] != "\n":
                i += 1
            continue
        if ch == '"':
            i += 1
            while i < n:
                if code[i] == '"':
                    if i + 1 < n and code[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(" ")
            continue
        if ch == "'":
            prev = code[i - 1] if i > 0 else ""
            if prev.isalnum() or prev in {"_", ")", "]", "}", "."}:
                out.append(ch)
                i += 1
                continue
            i += 1
            while i < n:
                if code[i] == "'":
                    if i + 1 < n and code[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(" ")
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def contains_keyboard_call(code: str) -> bool:
    """Return True if MATLAB code appears to invoke `keyboard` outside strings/comments."""
    stripped = strip_matlab_comments_and_strings(code)
    return _KEYBOARD_RE.search(stripped) is not None


def is_unsupported_input_error(text: str) -> bool:
    """Return True if an engine error message indicates unsupported `input()`."""
    lowered = text.lower()
    return any(marker in lowered for marker in _UNSUPPORTED_INPUT_MARKERS)


def format_execution_error(exc: MatlabExecutionError, captured_stderr: str) -> str:
    """Map MATLAB execution errors to clean, user-facing diagnostics."""
    combined = f"{exc}\n{captured_stderr}"
    if is_unsupported_input_error(combined):
        return UNSUPPORTED_INPUT_MESSAGE
    if captured_stderr.strip():
        return captured_stderr.rstrip("\n")
    return f"Error: {exc}"
