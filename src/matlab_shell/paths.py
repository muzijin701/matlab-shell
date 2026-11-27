"""OS standard user data directory helpers for matlab-shell."""

from __future__ import annotations

import os
import platform
from collections.abc import Mapping
from pathlib import Path

APP_DIR_NAME = "matlab-shell"


def get_data_dir(
    *,
    env: Mapping[str, str] | None = None,
    system: str | None = None,
    home: Path | None = None,
) -> Path:
    """Return the OS standard user data directory for matlab-shell."""
    env_map = os.environ if env is None else env
    sys_name = system or platform.system()
    home_dir = Path.home() if home is None else home

    if sys_name == "Windows":
        local_app_data = env_map.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else home_dir / "AppData" / "Local"
        return base / APP_DIR_NAME
    if sys_name == "Darwin":
        return home_dir / "Library" / "Application Support" / APP_DIR_NAME

    xdg_data_home = env_map.get("XDG_DATA_HOME")
    base = Path(xdg_data_home) if xdg_data_home else home_dir / ".local" / "share"
    return base / APP_DIR_NAME


def get_history_path(
    *,
    env: Mapping[str, str] | None = None,
    system: str | None = None,
    home: Path | None = None,
) -> Path:
    """Return the plain-text command history file path."""
    return get_data_dir(env=env, system=system, home=home) / "history.txt"


def get_config_dir(
    *,
    env: Mapping[str, str] | None = None,
    system: str | None = None,
    home: Path | None = None,
) -> Path:
    """Return the OS standard user configuration directory for matlab-shell."""
    env_map = os.environ if env is None else env
    sys_name = system or platform.system()
    home_dir = Path.home() if home is None else home

    if sys_name == "Windows":
        app_data = env_map.get("APPDATA")
        base = Path(app_data) if app_data else home_dir / "AppData" / "Roaming"
        return base / APP_DIR_NAME
    if sys_name == "Darwin":
        return home_dir / "Library" / "Application Support" / APP_DIR_NAME

    xdg_config_home = env_map.get("XDG_CONFIG_HOME")
    base = Path(xdg_config_home) if xdg_config_home else home_dir / ".config"
    return base / APP_DIR_NAME


def get_config_path(
    *,
    env: Mapping[str, str] | None = None,
    system: str | None = None,
    home: Path | None = None,
) -> Path:
    """Return the optional user configuration file path (`config.toml`)."""
    return get_config_dir(env=env, system=system, home=home) / "config.toml"
