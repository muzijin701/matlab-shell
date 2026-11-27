---
status: accepted
---

# Dynamically Load Local MATLAB Engine and Distribute Standalone CLI Binaries on Python 3.12

Instead of pinning a release-specific `matlabengine` package in `pyproject.toml` or bundling MATLAB binaries, `matlab-shell` discovers the user's local MATLAB installation at startup and dynamically loads its bundled Python engine bindings, targeting **MATLAB R2024a+** on a unified **Python 3.12** runtime. This allows shipping self-contained CLI executables in GitHub Releases alongside one-line install scripts, Python package installs (`uv` / `pipx` / `pip`), and later mainstream package managers (Scoop, Winget, Homebrew).

## Considered Options

- **Dynamic local engine loading + Python 3.12 standalone binaries (chosen)**: One artifact works across recent MATLAB releases (R2024a+) without bloating the release package or requiring end users to install Python or `uv`.
- **Pinning a PyPI `matlabengine==X.Y.*` dependency**: Couples the package to a single MATLAB release and breaks for users on other versions.
- **Bundling release-specific `matlabengine` binaries**: Multiplies release builds and artifact size across every MATLAB release.

## Consequences

- Minimum supported MATLAB release is **R2024a** (the earliest release officially supporting Python 3.12); older MATLAB releases are out of scope.
- Startup resolves the MATLAB root deterministically (`--matlab-root` → `MATLAB_SHELL_ROOT` / `MATLAB_ROOT` → `config.toml` → `PATH` → OS default paths / Windows registry) before importing `matlab.engine`.
- Public distribution channels (Winget, Homebrew, public one-line installer URLs) take effect once the repository is made public and publishes tagged releases.
