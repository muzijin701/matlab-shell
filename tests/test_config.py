"""Tests for optional `config.toml` loading and precedence."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from matlab_shell.cli import run_cli
from matlab_shell.config import load_config
from matlab_shell.errors import MatlabConfigError
from matlab_shell.paths import get_config_path
from tests.fakes import FakeSessionBackend
from tests.test_discovery import make_fake_matlab_root


def test_missing_config_returns_defaults_silently(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "nonexistent" / "config.toml")
    assert cfg.matlab_root is None
    assert cfg.editing_mode == "emacs"
    assert cfg.no_figure is False
    assert cfg.source_path is None


def test_config_applies_and_respects_precedence(tmp_path: Path) -> None:
    r_cfg = make_fake_matlab_root(tmp_path, "cfg_R2025a", release="R2025a")
    r_env = make_fake_matlab_root(tmp_path, "env_R2025b", release="R2025b")
    r_cli = make_fake_matlab_root(tmp_path, "cli_R2026a", release="R2026a")
    r_path = make_fake_matlab_root(tmp_path, "path_R2026a", release="R2026a", with_exe=True)

    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        f'matlab_root = "{r_cfg.as_posix()}"\nediting_mode = "vi"\nno_figure = true\n',
        encoding="utf-8",
    )

    loaded = load_config(cfg_file)
    assert loaded.editing_mode == "vi"
    assert loaded.no_figure is True

    # config.toml beats PATH and applies no_figure=true
    backend1 = FakeSessionBackend()
    code1 = run_cli(
        ["-c", "x=1"],
        backend=backend1,
        env={},
        cwd=tmp_path,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        which=lambda _cmd: str(r_path / "bin" / "matlab"),
        config_path=cfg_file,
    )
    assert code1 == 0
    assert backend1.start_calls[0].installation.root == r_cfg
    assert backend1.start_calls[0].no_figure is True

    # Environment beats config.toml
    backend2 = FakeSessionBackend()
    code2 = run_cli(
        ["-c", "x=1"],
        backend=backend2,
        env={"MATLAB_SHELL_ROOT": str(r_env)},
        cwd=tmp_path,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        config_path=cfg_file,
    )
    assert code2 == 0
    assert backend2.start_calls[0].installation.root == r_env

    # CLI --matlab-root beats environment and config.toml
    backend3 = FakeSessionBackend()
    code3 = run_cli(
        ["--matlab-root", str(r_cli), "-c", "x=1"],
        backend=backend3,
        env={"MATLAB_SHELL_ROOT": str(r_env)},
        cwd=tmp_path,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        config_path=cfg_file,
    )
    assert code3 == 0
    assert backend3.start_calls[0].installation.root == r_cli


@pytest.mark.parametrize(
    "bad_toml",
    [
        "not = valid = toml",
        'unknown_option = "foo"\n',
        'editing_mode = "nano"\n',
        'no_figure = "yes"\n',
        "matlab_root = 123\n",
    ],
)
def test_malformed_config_reports_path_and_nonzero_exit(
    tmp_path: Path,
    bad_toml: str,
) -> None:
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(bad_toml, encoding="utf-8")

    with pytest.raises(MatlabConfigError, match="config.toml"):
        load_config(cfg_file)

    err = io.StringIO()
    code = run_cli(
        ["-c", "x=1"],
        backend=FakeSessionBackend(),
        env={},
        cwd=tmp_path,
        stdout=io.StringIO(),
        stderr=err,
        config_path=cfg_file,
    )
    assert code == 1
    assert str(cfg_file) in err.getvalue()


def test_config_path_per_platform(tmp_path: Path) -> None:
    assert (
        get_config_path(env={"APPDATA": str(tmp_path / "Roaming")}, system="Windows", home=tmp_path)
        == tmp_path / "Roaming" / "matlab-shell" / "config.toml"
    )
    assert (
        get_config_path(env={}, system="Darwin", home=tmp_path)
        == tmp_path / "Library" / "Application Support" / "matlab-shell" / "config.toml"
    )
    assert (
        get_config_path(env={"XDG_CONFIG_HOME": str(tmp_path / "cfg")}, system="Linux", home=tmp_path)
        == tmp_path / "cfg" / "matlab-shell" / "config.toml"
    )
