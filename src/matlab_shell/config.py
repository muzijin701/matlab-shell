"""Optional user configuration loader (`config.toml`)."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from matlab_shell.errors import MatlabConfigError
from matlab_shell.paths import get_config_path

EditingMode = Literal["emacs", "vi"]
_ALLOWED_KEYS = frozenset({"matlab_root", "editing_mode", "no_figure"})


@dataclass(frozen=True)
class UserConfig:
    """Resolved optional user preferences."""

    matlab_root: str | None = None
    editing_mode: EditingMode = "emacs"
    no_figure: bool = False
    source_path: Path | None = None


def load_config(
    config_path: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    system: str | None = None,
    home: Path | None = None,
) -> UserConfig:
    """Load optional `config.toml`, returning defaults silently when absent."""
    path = config_path if config_path is not None else get_config_path(env=env, system=system, home=home)
    if not path.exists():
        return UserConfig()

    try:
        raw_text = path.read_text(encoding="utf-8")
        data = tomllib.loads(raw_text)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise MatlabConfigError(f"Invalid configuration file {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise MatlabConfigError(f"Invalid configuration file {path}: expected TOML table at root.")

    unknown_keys = sorted(set(data.keys()) - _ALLOWED_KEYS)
    if unknown_keys:
        joined = ", ".join(unknown_keys)
        raise MatlabConfigError(
            f"Unknown configuration key(s) in {path}: {joined}. "
            f"Allowed keys: {', '.join(sorted(_ALLOWED_KEYS))}."
        )

    matlab_root_raw = data.get("matlab_root")
    matlab_root: str | None = None
    if matlab_root_raw is not None:
        if not isinstance(matlab_root_raw, str) or not matlab_root_raw.strip():
            raise MatlabConfigError(
                f"Invalid 'matlab_root' in {path}: expected a non-empty string path."
            )
        matlab_root = matlab_root_raw.strip()

    editing_mode_raw = data.get("editing_mode", "emacs")
    if editing_mode_raw not in ("emacs", "vi"):
        raise MatlabConfigError(
            f"Invalid 'editing_mode' in {path}: expected 'emacs' or 'vi', got {editing_mode_raw!r}."
        )
    editing_mode: EditingMode = editing_mode_raw

    no_figure_raw = data.get("no_figure", False)
    if not isinstance(no_figure_raw, bool):
        raise MatlabConfigError(
            f"Invalid 'no_figure' in {path}: expected a boolean (true/false)."
        )

    return UserConfig(
        matlab_root=matlab_root,
        editing_mode=editing_mode,
        no_figure=no_figure_raw,
        source_path=path,
    )
