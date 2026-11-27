[中文](README.md)

# matlab-shell (`msh`)

An interactive terminal MATLAB CLI built with `uv` and Python. Drive a local MATLAB installation directly from Windows Terminal, macOS Terminal, or Linux shells with an interactive `>>` prompt and One-Shot Execution—without launching the heavy MATLAB Desktop GUI.

See the **[User Guide](docs/user-guide.en.md)** ([中文指南](docs/user-guide.md)) for full instructions and troubleshooting.

## Prerequisites

- A local licensed **MATLAB R2024a or later** installation (verified on MATLAB R2026a)
- For source/development: Python **3.12** (`>=3.12,<3.14`) and [`uv`](https://docs.astral.sh/uv/); standalone release archives bundle Python 3.12 so end users need no Python installation

## Installation

### 1. Package Managers (Recommended)

- **Windows (Scoop)**:
  ```powershell
  scoop bucket add muzijin701 https://github.com/muzijin701/scoop-bucket
  scoop install muzijin701/matlab-shell
  ```
- **macOS / Linux (Homebrew)**:
  ```sh
  brew tap muzijin701/tap
  brew install matlab-shell
  ```

### 2. One-Line Install Scripts

- **Windows (PowerShell)**:
  ```powershell
  irm https://raw.githubusercontent.com/muzijin701/matlab-shell/main/install.ps1 | iex
  ```
- **macOS / Linux**:
  ```sh
  curl -fsSL https://raw.githubusercontent.com/muzijin701/matlab-shell/main/install.sh | sh
  ```

### 3. GitHub Releases Standalone Archive

Download the archive for your OS/architecture from [Releases](https://github.com/muzijin701/matlab-shell/releases) (prebuilt binaries cover `windows-x86_64`, `linux-x86_64`, and `macos-arm64`; other architectures can install via `uv tool` / `pipx` below), extract it, and add the extracted folder to `PATH`.

### 4. Python Package Managers

```powershell
uv tool install --python 3.12 git+https://github.com/muzijin701/matlab-shell.git
# Or via pipx / pip
pipx install --python 3.12 git+https://github.com/muzijin701/matlab-shell.git
```

## Usage

```powershell
# Start an interactive >> Managed Session (auto-syncs terminal CWD)
msh

# One-Shot Execution (pipe-safe stdout; diagnostics go to stderr)
msh demo.m
msh -c "disp(1 + 1)"

# Run a script and drop into >> with Workspace preserved
msh -i demo.m

# Attach to an existing Shared Session (run `matlab.engine.shareEngine` in MATLAB first)
msh --attach
msh --attach MySession --cd

# Override MATLAB root or control native Figure windows
msh --matlab-root "C:\Program Files\MATLAB\R2026a" --no-figure
msh --figure
```

### Interactive Features

- **Multiline Auto-Continuation**: Automatically switches to `... ` on unclosed brackets, trailing `...`, or unmatched block keywords (`if`, `for`, `while`, `switch`, `try`, `function`, `classdef`) missing `end`; press `Alt+Enter` for manual newlines.
- **Tiered Tab Completion**: `.`-prefixed Meta-Commands, local paths inside quotes or `!` commands, and Workspace variables + local `.m` script names + common keywords, automatically following `cd` changes.
- **Meta-Commands & Intercepted Commands**: `.help`, `.sessions`, `.attach [name]`, `.vars`, `.clear`, `.info`, `.exit`; standalone `clc`, `exit`, and `quit` are handled locally in the terminal (without closing an external Shared Session).
- **History & Interruption**: Persistent cross-session history (`Up` / `Ctrl+R`); `Ctrl+C` cancels active evaluation or clears idle input; `Ctrl+D` or `exit` exits or detaches cleanly.

## Optional Configuration (`config.toml`)

Works with zero configuration. To persist defaults, create `config.toml` in your OS config directory (Windows: `%APPDATA%\matlab-shell\config.toml`; macOS: `~/Library/Application Support/matlab-shell/config.toml`; Linux: `~/.config/matlab-shell/config.toml`):

```toml
matlab_root = "C:\\Program Files\\MATLAB\\R2026a"
editing_mode = "emacs" # or "vi"
no_figure = false
```

Discovery precedence: `--matlab-root` > `MATLAB_SHELL_ROOT` / `MATLAB_ROOT` > `config.toml` > `PATH` > OS default install directories / Windows registry.

## Development & Building

```powershell
uv sync
uv run pytest -m "not matlab" -v
uv run pytest -m matlab -v           # requires local MATLAB R2024a+
uv run python scripts/build_release.py
```

## Conventions

- Domain terminology and architecture decisions live in [`GLOSSARY.md`](GLOSSARY.md) and `docs/adr/`.
- Issue tracking and agent workflow rules live in [`AGENTS.md`](AGENTS.md) and `docs/agents/`.
