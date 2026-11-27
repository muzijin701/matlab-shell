"""Tests for 5-level local MATLAB root discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from matlab_shell.discovery import discover_matlab, get_platform_arch
from matlab_shell.errors import MatlabDiscoveryError


def make_fake_matlab_root(
    base: Path,
    name: str,
    *,
    release: str | None = "R2026a",
    version: str | None = "26.1.0.1234",
    arch: str | None = None,
    with_exe: bool = False,
) -> Path:
    """Create a structurally valid fake MATLAB installation tree on disk."""
    resolved_arch = arch or get_platform_arch()
    root = base / name
    engine_dir = root / "extern" / "engines" / "python" / "dist" / "matlab" / "engine"
    engine_dir.mkdir(parents=True, exist_ok=True)
    (engine_dir / "__init__.py").write_text("# fake engine\n", encoding="utf-8")
    (root / "bin" / resolved_arch).mkdir(parents=True, exist_ok=True)

    if with_exe:
        exe_name = "matlab.exe" if resolved_arch == "win64" else "matlab"
        (root / "bin" / exe_name).write_text("", encoding="utf-8")

    if release is not None or version is not None:
        rel_xml = f"<release>{release}</release>" if release else ""
        ver_xml = f"<version>{version}</version>" if version else ""
        (root / "VersionInfo.xml").write_text(
            f"<MathWorks_version_info>{rel_xml}{ver_xml}</MathWorks_version_info>",
            encoding="utf-8",
        )
    return root


def test_discovery_priority_order(tmp_path: Path) -> None:
    cli_root = make_fake_matlab_root(tmp_path, "cli_matlab", release="R2024b")
    env_shell = make_fake_matlab_root(tmp_path, "env_shell_matlab", release="R2025a")
    env_matlab = make_fake_matlab_root(tmp_path, "env_matlab", release="R2025b")
    cfg_root = make_fake_matlab_root(tmp_path, "cfg_matlab", release="R2024a")
    path_root = make_fake_matlab_root(tmp_path, "path_matlab", release="R2026a", with_exe=True)
    default_root = make_fake_matlab_root(tmp_path, "default_matlab", release="R2026a")
    reg_root = make_fake_matlab_root(tmp_path, "reg_matlab", release="R2026b")

    exe_name = "matlab.exe" if get_platform_arch() == "win64" else "matlab"

    def which_fn(_cmd: str) -> str:
        return str(path_root / "bin" / exe_name)

    # 1. CLI wins over everything
    found = discover_matlab(
        cli_root=cli_root,
        env={"MATLAB_SHELL_ROOT": str(env_shell), "MATLAB_ROOT": str(env_matlab)},
        config_root=cfg_root,
        which=which_fn,
        default_candidates=[default_root],
        registry_candidates=[reg_root],
    )
    assert found.root == cli_root
    assert found.source == "cli"

    # 2a. MATLAB_SHELL_ROOT beats MATLAB_ROOT and below
    found = discover_matlab(
        env={"MATLAB_SHELL_ROOT": str(env_shell), "MATLAB_ROOT": str(env_matlab)},
        config_root=cfg_root,
        which=which_fn,
        default_candidates=[default_root],
        registry_candidates=[reg_root],
    )
    assert found.root == env_shell
    assert found.source == "env:MATLAB_SHELL_ROOT"

    # 2b. MATLAB_ROOT beats config and below
    found = discover_matlab(
        env={"MATLAB_ROOT": str(env_matlab)},
        config_root=cfg_root,
        which=which_fn,
        default_candidates=[default_root],
        registry_candidates=[reg_root],
    )
    assert found.root == env_matlab
    assert found.source == "env:MATLAB_ROOT"

    # 3. config_root beats PATH and below
    found = discover_matlab(
        env={},
        config_root=cfg_root,
        which=which_fn,
        default_candidates=[default_root],
        registry_candidates=[reg_root],
    )
    assert found.root == cfg_root
    assert found.source == "config"

    # 4. PATH beats default/registry
    found = discover_matlab(
        env={},
        which=which_fn,
        default_candidates=[default_root],
        registry_candidates=[reg_root],
    )
    assert found.root == path_root
    assert found.source == "path"

    # 5. Newest supported release wins across default_candidates + registry_candidates
    found = discover_matlab(
        env={},
        which=lambda _cmd: None,
        default_candidates=[default_root],
        registry_candidates=[reg_root],
    )
    assert found.root == reg_root
    assert found.release == "R2026b"
    assert found.source == "registry"


def test_discovery_picks_newest_supported_release(tmp_path: Path) -> None:
    r2024a = make_fake_matlab_root(tmp_path, "R2024a", release="R2024a")
    r2026a = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")
    r2025b = make_fake_matlab_root(tmp_path, "R2025b", release="R2025b")

    found = discover_matlab(
        env={},
        which=lambda _cmd: None,
        default_candidates=[r2024a, r2026a, r2025b],
        registry_candidates=[],
    )
    assert found.root == r2026a
    assert found.release == "R2026a"


def test_discovery_rejects_older_than_r2024a(tmp_path: Path) -> None:
    old_root = make_fake_matlab_root(tmp_path, "R2023b", release="R2023b", with_exe=True)

    with pytest.raises(MatlabDiscoveryError, match="R2024a"):
        discover_matlab(cli_root=old_root, env={})

    with pytest.raises(MatlabDiscoveryError, match="R2023b"):
        discover_matlab(
            env={},
            which=lambda _cmd: str(old_root / "bin" / "matlab"),
            default_candidates=[old_root],
            registry_candidates=[],
        )


def test_explicit_invalid_root_fails_without_fallback(tmp_path: Path) -> None:
    valid_fallback = make_fake_matlab_root(tmp_path, "R2026a", release="R2026a")
    bogus = tmp_path / "does_not_exist"

    with pytest.raises(MatlabDiscoveryError, match="--matlab-root|cli"):
        discover_matlab(
            cli_root=bogus,
            env={},
            which=lambda _cmd: None,
            default_candidates=[valid_fallback],
            registry_candidates=[],
        )

    with pytest.raises(MatlabDiscoveryError, match="MATLAB_SHELL_ROOT"):
        discover_matlab(
            env={"MATLAB_SHELL_ROOT": str(bogus)},
            which=lambda _cmd: None,
            default_candidates=[valid_fallback],
            registry_candidates=[],
        )


def test_missing_matlab_error_has_actionable_guidance(tmp_path: Path) -> None:
    with pytest.raises(MatlabDiscoveryError) as exc_info:
        discover_matlab(
            env={},
            which=lambda _cmd: None,
            default_candidates=[tmp_path / "missing"],
            registry_candidates=[],
        )

    msg = str(exc_info.value)
    assert "R2024a" in msg
    assert "--matlab-root" in msg
    assert "MATLAB_SHELL_ROOT" in msg
