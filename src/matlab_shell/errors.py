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
    at_line_start = True
    in_block_comment = False
    while i < n:
        ch = code[i]

        if in_block_comment:
            if at_line_start:
                j = i
                while j < n and code[j] in " \t":
                    j += 1
                if code[j : j + 2] == "%}":
                    k = j + 2
                    while k < n and code[k] in " \t\r":
                        k += 1
                    if k == n or code[k] == "\n":
                        in_block_comment = False
                        out.append("\n" if k < n and code[k] == "\n" else " ")
                        i = k + 1 if k < n and code[k] == "\n" else k
                        at_line_start = True
                        continue
            if ch == "\n":
                out.append("\n")
                at_line_start = True
            else:
                at_line_start = False
            i += 1
            continue

        if at_line_start:
            j = i
            while j < n and code[j] in " \t":
                j += 1
            if code[j : j + 2] == "%{":
                k = j + 2
                while k < n and code[k] in " \t\r":
                    k += 1
                if k == n or code[k] == "\n":
                    in_block_comment = True
                    out.append("\n" if k < n and code[k] == "\n" else " ")
                    i = k + 1 if k < n and code[k] == "\n" else k
                    at_line_start = True
                    continue

        if ch == "\n":
            out.append(ch)
            at_line_start = True
            i += 1
            continue

        if ch in " \t\r":
            out.append(ch)
            i += 1
            continue

        at_line_start = False

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
                if code[i] == "\n":
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
                if code[i] == "\n":
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
    for match in _KEYBOARD_RE.finditer(stripped):
        idx = match.start() - 1
        while idx >= 0 and stripped[idx].isspace():
            idx -= 1
        if idx >= 0 and stripped[idx] == ".":
            continue
        return True
    return False


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
