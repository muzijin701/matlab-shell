"""Lightweight MATLAB statement completeness detection for multiline REPL input."""

from __future__ import annotations

import re

_ALWAYS_BLOCK_OPENERS = frozenset(
    {
        "if",
        "for",
        "parfor",
        "while",
        "switch",
        "try",
        "function",
        "classdef",
        "spmd",
    }
)
_CLASSDEF_SECTION_OPENERS = frozenset(
    {
        "properties",
        "methods",
        "events",
        "enumeration",
    }
)

_META_CMD_RE = re.compile(r"^\s*\.[A-Za-z]")
_OPEN_BRACKETS = {"(", "[", "{"}
_CLOSE_BRACKETS = {")", "]", "}"}


def is_complete_statement(code: str) -> bool:
    """Return True if MATLAB code is syntactically ready to submit, False if incomplete."""
    stripped = code.strip()
    if not stripped:
        return True
    if stripped.startswith("!") or _META_CMD_RE.match(code):
        return True

    bracket_depth = 0
    block_stack: list[str] = []
    trailing_ellipsis = False
    in_block_comment = False
    prev_non_ws = ""

    i = 0
    n = len(code)
    at_line_start = True

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
                        i = k + 1 if k < n and code[k] == "\n" else k
                        at_line_start = True
                        prev_non_ws = ""
                        continue
            if ch == "\n":
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
                    i = k + 1 if k < n and code[k] == "\n" else k
                    at_line_start = True
                    prev_non_ws = ""
                    continue

        if ch == "\n":
            at_line_start = True
            if not trailing_ellipsis:
                prev_non_ws = ""
            i += 1
            continue

        if ch in " \t\r":
            i += 1
            continue

        at_line_start = False

        # Line continuation `...` (everything after `...` on the line is a comment)
        if code[i : i + 3] == "...":
            trailing_ellipsis = True
            while i < n and code[i] != "\n":
                i += 1
            continue

        # Single-line comment `%` (does not clear trailing_ellipsis on this line)
        if ch == "%":
            while i < n and code[i] != "\n":
                i += 1
            continue

        trailing_ellipsis = False

        # Double-quoted string literal
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
            prev_non_ws = "str"
            continue

        # Single-quoted char vector vs transpose operator
        if ch == "'":
            prev = code[i - 1] if i > 0 else ""
            if prev.isalnum() or prev in {"_", ")", "]", "}", "."}:
                i += 1
                prev_non_ws = ch
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
            prev_non_ws = "str"
            continue

        if ch in _OPEN_BRACKETS:
            bracket_depth += 1
            prev_non_ws = ch
            i += 1
            continue

        if ch in _CLOSE_BRACKETS:
            if bracket_depth > 0:
                bracket_depth -= 1
            prev_non_ws = ch
            i += 1
            continue

        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (code[i].isalnum() or code[i] == "_"):
                i += 1
            word = code[start:i]
            is_field_access = prev_non_ws == "."
            if bracket_depth == 0 and not is_field_access:
                if word in _ALWAYS_BLOCK_OPENERS:
                    block_stack.append(word)
                elif (
                    word in _CLASSDEF_SECTION_OPENERS
                    and block_stack
                    and block_stack[-1] == "classdef"
                ):
                    block_stack.append(word)
                elif word == "end" and block_stack:
                    block_stack.pop()
            prev_non_ws = "id"
            continue

        prev_non_ws = ch
        i += 1

    if in_block_comment or trailing_ellipsis or bracket_depth > 0 or bool(block_stack):
        return False
    return True
