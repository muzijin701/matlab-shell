"""Tiered zero-lag Tab completion for matlab-shell."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

META_COMMAND_NAMES: tuple[str, ...] = (
    ".help",
    ".sessions",
    ".attach",
    ".vars",
    ".clear",
    ".info",
    ".exit",
)

MATLAB_KEYWORDS: tuple[str, ...] = (
    "break",
    "case",
    "catch",
    "classdef",
    "clear",
    "clc",
    "continue",
    "disp",
    "else",
    "elseif",
    "end",
    "error",
    "events",
    "exit",
    "eye",
    "false",
    "for",
    "fprintf",
    "function",
    "global",
    "if",
    "length",
    "linspace",
    "load",
    "methods",
    "ones",
    "otherwise",
    "parfor",
    "persistent",
    "plot",
    "properties",
    "pwd",
    "quit",
    "return",
    "run",
    "save",
    "size",
    "spmd",
    "sprintf",
    "switch",
    "true",
    "try",
    "warning",
    "while",
    "who",
    "whos",
    "zeros",
)

_META_LINE_RE = re.compile(r"^\s*(\.[A-Za-z0-9_-]*)$")
_IDENT_SUFFIX_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)$")


def _extract_open_quote_prefix(text_before_cursor: str) -> str | None:
    """Return unclosed quote content if cursor is inside `'...'` or `\"...\"`."""
    i = 0
    n = len(text_before_cursor)
    while i < n:
        ch = text_before_cursor[i]
        if ch == '"':
            start = i + 1
            i += 1
            while i < n:
                if text_before_cursor[i] == '"':
                    if i + 1 < n and text_before_cursor[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            else:
                return text_before_cursor[start:]
            continue
        if ch == "'":
            prev = text_before_cursor[i - 1] if i > 0 else ""
            if prev.isalnum() or prev in {"_", ")", "]", "}", "."}:
                i += 1
                continue
            start = i + 1
            i += 1
            while i < n:
                if text_before_cursor[i] == "'":
                    if i + 1 < n and text_before_cursor[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            else:
                return text_before_cursor[start:]
            continue
        i += 1
    return None


def _list_path_completions(raw_prefix: str, cwd: Path) -> list[tuple[str, int]]:
    """Return (completion_text, start_position) pairs for a filesystem prefix."""
    normalized = raw_prefix.replace("\\", "/")
    if "/" in normalized:
        dir_part, name_prefix = normalized.rsplit("/", 1)
        if dir_part == "":
            search_dir = Path("/")
        elif len(dir_part) == 2 and dir_part[1] == ":" and dir_part[0].isalpha():
            search_dir = Path(f"{dir_part}/")
        else:
            candidate_dir = Path(dir_part)
            search_dir = candidate_dir if candidate_dir.is_absolute() else cwd / dir_part
    else:
        name_prefix = normalized
        search_dir = cwd

    if not search_dir.is_dir():
        return []

    results: list[tuple[str, int]] = []
    try:
        entries = sorted(search_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        return []

    for entry in entries:
        if name_prefix and not entry.name.lower().startswith(name_prefix.lower()):
            continue
        suffix = "/" if entry.is_dir() else ""
        results.append((entry.name + suffix, -len(name_prefix)))
    return results


class MatlabCompleter(Completer):
    """Three-tier non-blocking completer: Meta-Commands, paths, and MATLAB symbols."""

    def __init__(
        self,
        *,
        get_workspace_vars: Callable[[], Sequence[str]],
        get_cwd: Callable[[], Path],
        meta_commands: Sequence[str] = META_COMMAND_NAMES,
    ) -> None:
        self._get_workspace_vars = get_workspace_vars
        self._get_cwd = get_cwd
        self._meta_commands = tuple(meta_commands)

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,
    ) -> Iterable[Completion]:
        line = document.current_line_before_cursor

        # Tier 1: `.`-prefixed Meta-Commands
        meta_match = _META_LINE_RE.match(line)
        if meta_match is not None:
            prefix = meta_match.group(1)
            for cmd in self._meta_commands:
                if cmd.startswith(prefix.lower()):
                    yield Completion(cmd, start_position=-len(prefix))
            return

        # Tier 2: Path context inside quotes or after `!` shell escape
        quote_prefix = _extract_open_quote_prefix(line)
        if quote_prefix is not None:
            for text, start_pos in _list_path_completions(quote_prefix, self._get_cwd()):
                yield Completion(text, start_position=start_pos)
            return

        stripped_line = line.lstrip()
        if stripped_line.startswith("!"):
            shell_part = stripped_line[1:]
            token = shell_part.split()[-1] if shell_part and not shell_part.endswith(" ") else ""
            for text, start_pos in _list_path_completions(token, self._get_cwd()):
                yield Completion(text, start_position=start_pos)
            return

        # Tier 3: MATLAB Workspace vars + local .m files + keywords
        ident_match = _IDENT_SUFFIX_RE.search(line)
        if ident_match is None:
            return
        prefix = ident_match.group(1)
        lowered = prefix.lower()

        seen: set[str] = set()
        candidates: list[str] = []

        for var in self._get_workspace_vars():
            if var not in seen:
                seen.add(var)
                candidates.append(var)

        try:
            cwd = self._get_cwd()
            if cwd.is_dir():
                for entry in sorted(os.scandir(cwd), key=lambda e: e.name.lower()):
                    if entry.is_file() and entry.name.lower().endswith(".m"):
                        stem = entry.name[:-2]
                        if stem not in seen:
                            seen.add(stem)
                            candidates.append(stem)
        except OSError:
            pass

        for kw in MATLAB_KEYWORDS:
            if kw not in seen:
                seen.add(kw)
                candidates.append(kw)

        for item in candidates:
            if item.lower().startswith(lowered):
                yield Completion(item, start_position=-len(prefix))
