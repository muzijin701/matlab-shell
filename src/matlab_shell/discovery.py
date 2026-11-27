"""Local MATLAB installation discovery (MATLAB R2024a+)."""

from __future__ import annotations

import os
import platform
import re
import shutil
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from matlab_shell.errors import MatlabDiscoveryError

MIN_SUPPORTED_RELEASE: tuple[int, int] = (2024, 1)
MIN_SUPPORTED_RELEASE_NAME = "R2024a"

_RELEASE_RE = re.compile(r"^R(\d{4})([ab])$", re.IGNORECASE)
_EMBEDDED_RELEASE_RE = re.compile(r"R\d{4}[ab]", re.IGNORECASE)


@dataclass(frozen=True)
class MatlabInstallation:
    """Resolved local MATLAB installation metadata."""

    root: Path
    release: str | None
    version: str | None
    source: str


def get_platform_arch(
    system: str | None = None,
    machine: str | None = None,
) -> str:
    """Return MATLAB's platform architecture folder name."""
    sys_name = system or platform.system()
    mach_name = (machine or platform.machine()).lower()
    if sys_name == "Windows":
        return "win64"
    if sys_name == "Darwin":
        return "maca64" if mach_name in {"arm64", "aarch64"} else "maci64"
    return "glnxa64"


def parse_release_key(release: str | None) -> tuple[int, int] | None:
    """Parse a release label like 'R2026a' into a sortable (year, half) tuple."""
    if not release:
        return None
    match = _RELEASE_RE.match(release.strip())
    if not match:
        return None
    year = int(match.group(1))
    half = 1 if match.group(2).lower() == "a" else 2
    return (year, half)


def is_supported_release(release: str | None) -> bool:
    """Return True when the release is >= R2024a (or unknown)."""
    key = parse_release_key(release)
    if key is None:
        return True
    return key >= MIN_SUPPORTED_RELEASE


def read_version_info(root: Path) -> tuple[str | None, str | None]:
    """Read (release, version) from VersionInfo.xml, falling back to folder name."""
    release: str | None = None
    version: str | None = None
    info_path = root / "VersionInfo.xml"
    if info_path.is_file():
        try:
            tree = ET.parse(info_path)
            xml_root = tree.getroot()
            rel_text = xml_root.findtext("release")
            ver_text = xml_root.findtext("version")
            if rel_text and rel_text.strip():
                release = rel_text.strip()
            if ver_text and ver_text.strip():
                version = ver_text.strip()
        except ET.ParseError:
            pass
    if release is None:
        match = _EMBEDDED_RELEASE_RE.search(root.name)
        if match:
            raw = match.group(0)
            release = f"R{raw[1:5]}{raw[5].lower()}"
    return release, version


def validate_matlab_root(
    root: Path,
    *,
    arch: str | None = None,
) -> tuple[bool, str | None]:
    """Check whether a directory is a structurally valid MATLAB root."""
    if not root.is_dir():
        return False, f"directory does not exist: {root}"
    engine_init = (
        root / "extern" / "engines" / "python" / "dist" / "matlab" / "engine" / "__init__.py"
    )
    if not engine_init.is_file():
        return False, f"missing Python engine files under {root / 'extern' / 'engines' / 'python'}"
    resolved_arch = arch or get_platform_arch()
    bin_dir = root / "bin" / resolved_arch
    if not bin_dir.is_dir():
        return False, f"missing architecture binary directory: {bin_dir}"
    return True, None


def root_from_executable(executable: Path) -> Path | None:
    """Walk up from a matlab executable path to locate the MATLAB root."""
    try:
        resolved = executable.resolve()
    except OSError:
        resolved = executable
    current = resolved.parent if resolved.is_file() or not resolved.exists() else resolved
    for candidate in (current, *current.parents):
        if (candidate / "extern" / "engines" / "python" / "dist").is_dir():
            return candidate
    return None


def _scan_windows_registry() -> list[Path]:
    """Scan Windows registry for installed MathWorks MATLAB roots."""
    if platform.system() != "Windows":
        return []
    try:
        import winreg
    except ImportError:
        return []

    roots: list[Path] = []
    key_path = r"SOFTWARE\MathWorks\MATLAB"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as base_key:
            index = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(base_key, index)
                except OSError:
                    break
                index += 1
                try:
                    with winreg.OpenKey(base_key, subkey_name) as subkey:
                        val, _ = winreg.QueryValueEx(subkey, "MATLABROOT")
                        if isinstance(val, str) and val.strip():
                            roots.append(Path(val.strip()))
                except OSError:
                    continue
    except OSError:
        return []
    return roots


def _default_search_candidates(system: str | None = None) -> list[Path]:
    """Return candidate MATLAB installation directories in OS default locations."""
    sys_name = system or platform.system()
    candidates: list[Path] = []
    if sys_name == "Windows":
        for base in (Path(r"C:\Program Files\MATLAB"), Path(r"D:\Program Files\MATLAB")):
            if base.is_dir():
                candidates.extend(sorted(base.glob("R*")))
    elif sys_name == "Darwin":
        apps = Path("/Applications")
        if apps.is_dir():
            candidates.extend(sorted(apps.glob("MATLAB_R*.app")))
    else:
        for base in (Path("/usr/local/MATLAB"), Path("/opt/MATLAB")):
            if base.is_dir():
                candidates.extend(sorted(base.glob("R*")))
    return candidates


def _build_explicit_installation(
    raw_root: str | Path,
    *,
    source: str,
    arch: str,
) -> MatlabInstallation:
    """Validate an explicitly configured MATLAB root or fail with MatlabDiscoveryError."""
    root = Path(raw_root).expanduser()
    valid, reason = validate_matlab_root(root, arch=arch)
    if not valid:
        raise MatlabDiscoveryError(
            f"Invalid MATLAB root from {source} ({root}): {reason}. "
            f"Please point to a valid MATLAB {MIN_SUPPORTED_RELEASE_NAME}+ installation."
        )
    release, version = read_version_info(root)
    if not is_supported_release(release):
        raise MatlabDiscoveryError(
            f"MATLAB {release} at {root} (from {source}) is not supported. "
            f"matlab-shell requires MATLAB {MIN_SUPPORTED_RELEASE_NAME} or newer."
        )
    return MatlabInstallation(root=root, release=release, version=version, source=source)


def discover_matlab(
    *,
    cli_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    config_root: str | Path | None = None,
    which: Callable[[str], str | None] | None = None,
    default_candidates: Sequence[Path] | None = None,
    registry_candidates: Sequence[Path] | None = None,
    arch: str | None = None,
) -> MatlabInstallation:
    """Locate a supported local MATLAB R2024a+ installation using the 5-level chain."""
    resolved_arch = arch or get_platform_arch()
    env_map = os.environ if env is None else env
    which_fn = shutil.which if which is None else which

    # 1. --matlab-root CLI flag
    if cli_root is not None and str(cli_root).strip():
        return _build_explicit_installation(cli_root, source="cli", arch=resolved_arch)

    # 2. Environment variables: MATLAB_SHELL_ROOT > MATLAB_ROOT
    for env_var in ("MATLAB_SHELL_ROOT", "MATLAB_ROOT"):
        val = env_map.get(env_var)
        if val and val.strip():
            return _build_explicit_installation(
                val.strip(),
                source=f"env:{env_var}",
                arch=resolved_arch,
            )

    # 3. Optional config.toml matlab_root
    if config_root is not None and str(config_root).strip():
        return _build_explicit_installation(config_root, source="config", arch=resolved_arch)

    rejected_old: list[str] = []

    # 4. matlab executable in PATH
    exe_path = which_fn("matlab")
    if exe_path:
        inferred_root = root_from_executable(Path(exe_path))
        if inferred_root is not None:
            valid, _ = validate_matlab_root(inferred_root, arch=resolved_arch)
            if valid:
                release, version = read_version_info(inferred_root)
                if is_supported_release(release):
                    return MatlabInstallation(
                        root=inferred_root,
                        release=release,
                        version=version,
                        source="path",
                    )
                rejected_old.append(f"{release} at {inferred_root} (from PATH)")

    # 5. OS default directories and Windows registry (newest supported release wins)
    defaults = (
        list(_default_search_candidates())
        if default_candidates is None
        else list(default_candidates)
    )
    regs = (
        _scan_windows_registry()
        if registry_candidates is None
        else list(registry_candidates)
    )

    tagged_candidates: list[tuple[Path, str]] = [
        *((path, "default-dir") for path in defaults),
        *((path, "registry") for path in regs),
    ]

    seen: set[Path] = set()
    valid_installations: list[MatlabInstallation] = []
    for raw_path, src in tagged_candidates:
        try:
            resolved_path = raw_path.resolve()
        except OSError:
            resolved_path = raw_path
        if resolved_path in seen:
            continue
        seen.add(resolved_path)

        valid, _ = validate_matlab_root(raw_path, arch=resolved_arch)
        if not valid:
            continue
        release, version = read_version_info(raw_path)
        if not is_supported_release(release):
            rejected_old.append(f"{release} at {raw_path} (from {src})")
            continue
        valid_installations.append(
            MatlabInstallation(root=raw_path, release=release, version=version, source=src)
        )

    if valid_installations:
        valid_installations.sort(
            key=lambda item: parse_release_key(item.release) or (0, 0),
            reverse=True,
        )
        return valid_installations[0]

    details = ""
    if rejected_old:
        details = f" Ignored older unsupported releases: {'; '.join(rejected_old)}."
    raise MatlabDiscoveryError(
        f"Could not find a supported MATLAB ({MIN_SUPPORTED_RELEASE_NAME}+) installation.{details} "
        "Pass --matlab-root <path> or set the MATLAB_SHELL_ROOT environment variable."
    )
