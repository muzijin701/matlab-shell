"""Build standalone Python 3.12 release archives for matlab-shell (`msh` + `matlab-shell`)."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _platform_tag() -> str:
    sys_name = platform.system().lower()
    if sys_name == "darwin":
        sys_name = "macos"
    machine = platform.machine().lower()
    arch_map = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}
    arch = arch_map.get(machine, machine)
    return f"{sys_name}-{arch}"


def _write_sha256sums(dist_dir: Path, archive_path: Path) -> Path:
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    sums_path = dist_dir / "SHA256SUMS.txt"
    existing = []
    if sums_path.is_file():
        existing = [
            line
            for line in sums_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.endswith(f"  {archive_path.name}")
        ]
    existing.append(f"{digest}  {archive_path.name}")
    sums_path.write_text("\n".join(sorted(existing)) + "\n", encoding="utf-8")
    return sums_path


def build() -> Path:
    version = _read_version()
    tag = _platform_tag()
    build_dir = ROOT / "build" / "release"
    dist_dir = ROOT / "dist"
    bundle_name = f"matlab-shell-{version}-{tag}"
    work_dir = build_dir / "work"
    stage_dir = build_dir / "stage"

    for directory in (work_dir, stage_dir):
        if directory.exists():
            shutil.rmtree(directory)
    build_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    entry_script = build_dir / "_entry.py"
    entry_script.write_text(
        "from matlab_shell.cli import main\n\nif __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )

    spec_path = build_dir / "matlab-shell.spec"
    src_path = (ROOT / "src").as_posix()
    entry_posix = entry_script.as_posix()
    spec_path.write_text(
        f"""# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    [{entry_posix!r}],
    pathex=[{src_path!r}],
    binaries=[],
    datas=[],
    hiddenimports=['pygments.lexers.matlab'],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['matlab'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe_main = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='matlab-shell',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

exe_short = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='msh',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe_main,
    exe_short,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name={bundle_name!r},
)
""",
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--workpath",
            str(work_dir),
            "--distpath",
            str(stage_dir),
            str(spec_path),
        ],
        cwd=ROOT,
        check=True,
    )

    bundle_dir = stage_dir / bundle_name
    if platform.system() == "Windows":
        archive_path = dist_dir / f"{bundle_name}.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for item in sorted(bundle_dir.rglob("*")):
                if item.is_file():
                    zf.write(item, arcname=item.relative_to(bundle_dir))
    else:
        archive_path = dist_dir / f"{bundle_name}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tf:
            for entry in sorted(bundle_dir.iterdir()):
                tf.add(entry, arcname=entry.name)

    # Keep an unzipped copy under dist/<bundle_name> for quick local verification
    unzipped_dist = dist_dir / bundle_name
    if unzipped_dist.exists():
        shutil.rmtree(unzipped_dist)
    shutil.copytree(bundle_dir, unzipped_dist)

    sums_path = _write_sha256sums(dist_dir, archive_path)
    print(f"Built archive: {archive_path}")
    print(f"Unpacked dir:  {unzipped_dist}")
    print(f"Checksums:     {sums_path}")
    return archive_path


if __name__ == "__main__":
    os.chdir(ROOT)
    build()
