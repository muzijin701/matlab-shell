[中文](user-guide.md)

# matlab-shell (`msh`) User Guide

`matlab-shell` (short command: `msh`) is an interactive terminal CLI that drives a local MATLAB installation directly from Windows Terminal, macOS Terminal, or Linux shells—without launching the heavy MATLAB Desktop GUI.

---

## 1. Prerequisites & Installation

### Requirements

- A local licensed **MATLAB R2024a or later** installation (verified on MATLAB R2026a).
- **No Python or `uv` required** when using standalone release archives (Python 3.12 runtime is bundled).
- Source / `uv tool` / `pipx` installations require Python **3.12** (`>=3.12,<3.14`).

### Prebuilt Binary Coverage

GitHub Releases currently ships standalone archives for:

- `windows-x86_64` (`.zip`)
- `linux-x86_64` (`.tar.gz`)
- `macos-arm64` (Apple Silicon, `.tar.gz`)

For other platforms or architectures (such as Intel macOS `x86_64` or Linux `arm64`), install via `uv tool` or `pipx` with Python 3.12 (Method 4 below).

### Installation Methods

1. **Package Managers (Recommended)**:
   - Windows (Scoop):
     ```powershell
     scoop bucket add muzijin701 https://github.com/muzijin701/scoop-bucket
     scoop install muzijin701/matlab-shell
     ```
   - macOS / Linux (Homebrew):
     ```sh
     brew tap muzijin701/tap
     brew install matlab-shell
     ```

2. **One-Line Install Scripts** (automatically verifies Release `SHA256SUMS.txt`):
   - Windows (PowerShell):
     ```powershell
     irm https://raw.githubusercontent.com/muzijin701/matlab-shell/main/install.ps1 | iex
     ```
   - macOS / Linux:
     ```sh
     curl -fsSL https://raw.githubusercontent.com/muzijin701/matlab-shell/main/install.sh | sh
     ```

   > **Safety note for custom install paths**: By default, files are placed in a dedicated folder (`%LOCALAPPDATA%\matlab-shell\bin` on Windows; `~/.local/share/matlab-shell/bin` on Unix). If you override `MATLAB_SHELL_INSTALL_DIR`, it must be empty or contain only an existing `matlab-shell` installation; if unrelated files are present, the installer aborts without deleting anything.

3. **GitHub Releases Archive**: Download the archive for your OS/architecture from [Releases](https://github.com/muzijin701/matlab-shell/releases), extract it, and add the extracted directory to `PATH`.

4. **Python Toolchain**:
   ```powershell
   uv tool install --python 3.12 git+https://github.com/muzijin701/matlab-shell.git
   # or
   pipx install --python 3.12 git+https://github.com/muzijin701/matlab-shell.git
   ```

Verify installation:

```powershell
msh --version
```

---

## 2. Launch Modes & CLI Options

| Use Case | Example | Behavior |
|---|---|---|
| Interactive REPL | `msh` | Starts a **Managed Session** and syncs to your current terminal directory |
| One-Shot script | `msh demo.m` | Runs `demo.m` and exits; MATLAB output goes to `stdout`, diagnostics to `stderr` |
| One-Shot inline command | `msh -c "disp(1 + 1)"` | Ideal for automation and piping (e.g., `msh -c "disp(pi)" > out.txt`) |
| Run then stay interactive | `msh -i demo.m` or `msh -i -c "x = 1;"` | Keeps the **Workspace** and drops into the `>>` prompt |
| Attach to open MATLAB | `msh --attach` / `msh --attach MySession` | Connects to an external **Shared Session**; detaches cleanly on exit |
| Explicit MATLAB root | `msh --matlab-root "C:\Program Files\MATLAB\R2026a"` | Overrides auto-discovery and environment variables |
| Control Figure windows | `msh --no-figure` / `msh --figure` | Disables or forces native Figure windows (overrides `config.toml`) |

> Note: `msh` and `matlab-shell` are identical CLI entry points.

---

## 3. Interactive Features

### Multiline Auto-Continuation

Pressing `Enter` at `>>` automatically continues to `... ` when your input is incomplete:

- Unclosed brackets: `(...)`, `[...]`, `{...}`
- Trailing line continuation `...` (including trailing comments like `... % note`)
- Open blocks missing `end`: `if`, `for`, `parfor`, `while`, `switch`, `try`, `function`, `classdef`, `spmd` (plus `properties`/`methods`/`events`/`enumeration` inside `classdef`)

Press `Alt+Enter` at any time to insert a manual newline.

### Tiered Tab Completion

Pressing `Tab` resolves candidates locally with zero engine lag:

1. **Meta-Commands**: Lines starting with `.` (e.g., `.s` + `Tab` → `.sessions`).
2. **Filesystem Paths**: Inside single/double quotes (e.g., `run('sub/`) or after `!` shell escapes, resolved against the live **Session** working directory.
3. **MATLAB Symbols**: Current **Workspace** variables, `.m` files in the active **Session** directory, and common MATLAB keywords.

Running `cd` inside the REPL automatically updates the cached **Session** working directory for both Tab completion and `.info`.

### Meta-Commands vs. Intercepted Commands

All standard MATLAB statements (`clear`, `whos`, `cd`, `plot`, etc.) pass straight through to the **Session**. Only two small local command sets are handled by `matlab-shell`:

1. **Meta-Commands (`.`-prefixed)**

| Command | Description |
|---|---|
| `.help` | Show built-in commands and keyboard shortcuts |
| `.sessions` | List available **Shared Sessions** (marking the active one) |
| `.attach [name]` | Switch to a **Shared Session**; prompts with a numbered picker when multiple exist |
| `.vars` | Print **Workspace** variable summary (`whos`) |
| `.clear` | Clear the terminal viewport and scrollback buffer |
| `.info` | Display MATLAB root, release, version, discovery source, Session type, and live `Session CWD` |
| `.exit` | Exit `matlab-shell` (or detach from a **Shared Session**) |

2. **Intercepted Commands (Standalone MATLAB keywords)**

When typed **alone** at the interactive prompt (with optional trailing `;`):

- `clc` / `clc;`: Clears the terminal viewport and scrollback buffer locally (matching `.clear`; in a **Shared Session**, it does not clear the external MATLAB Desktop Command Window).
- `exit` / `quit` (with optional `;`): Exits `matlab-shell` or detaches cleanly from a **Shared Session** without shutting down external MATLAB.

> Note: Compound statements (such as `x = 1; clc`) and `.m` scripts are forwarded unmodified to MATLAB; `clc` inside `.m` scripts remains a no-op under the headless engine.

### Shell Passthrough, History & Shortcuts

- **Shell Passthrough**: Lines starting with `!` (e.g., `!git status`, `!dir`) are forwarded to MATLAB and stream output directly.
- **Persistent History**: Stored as plain text across sessions and searchable with `Up`/`Down` or `Ctrl+R`:
  - Windows: `%LOCALAPPDATA%\matlab-shell\history.txt`
  - macOS: `~/Library/Application Support/matlab-shell/history.txt`
  - Linux: `${XDG_DATA_HOME:-~/.local/share}/matlab-shell/history.txt`
- **Cancellation & Exit**:
  - `Ctrl+C` while idle: Clears/cancels the current input line without exiting.
  - `Ctrl+C` while evaluating: Sends an asynchronous cancellation request to the MATLAB Engine.
  - `Ctrl+D` on an empty prompt: Exits (or detaches from a **Shared Session**).

---

## 4. Working with a Shared Session

To share a Workspace with an already-open MATLAB Desktop or avoid startup time:

1. In MATLAB Desktop's Command Window, share the engine:
   ```matlab
   matlab.engine.shareEngine
   % Or with an explicit name:
   matlab.engine.shareEngine('MySession')
   ```
2. Attach from your terminal:
   ```powershell
   msh --attach                 # auto-attaches if 1 exists; prompts if multiple
   msh --attach MySession       # attach by name
   msh --attach MySession --cd  # also sync MATLAB CWD to terminal CWD
   ```
3. By default, `--attach` and in-REPL `.attach` preserve the target **Shared Session**'s existing working directory unless `--cd` is passed.
4. Exiting via `.exit`, `exit`, or `Ctrl+D` only detaches the terminal client—MATLAB Desktop stays open.

---

## 5. Configuration & MATLAB Discovery

### Optional `config.toml`

`matlab-shell` works with zero configuration. To save defaults, create `config.toml` at:

- Windows: `%APPDATA%\matlab-shell\config.toml`
- macOS: `~/Library/Application Support/matlab-shell/config.toml`
- Linux: `${XDG_CONFIG_HOME:-~/.config}/matlab-shell/config.toml`

Supported keys:

```toml
# Explicit MATLAB installation root
matlab_root = "C:\\Program Files\\MATLAB\\R2026a"

# Line-editing mode: "emacs" (default) or "vi"
editing_mode = "emacs"

# Disable native Figure windows by default (override per-run with --figure)
no_figure = false
```

### 5-Level Discovery Precedence

`matlab-shell` locates **MATLAB R2024a+** in this order (explicit invalid or older roots fail fast without silent fallback):

1. `--matlab-root <path>` CLI flag
2. `MATLAB_SHELL_ROOT`, then `MATLAB_ROOT` environment variables
3. `matlab_root` in `config.toml`
4. `matlab` executable on `PATH`
5. OS default install directories and Windows Registry (newest supported release wins)

---

## 6. Known Limitations & Troubleshooting

### Why do `input()` and `keyboard` not work interactively?

Because `matlab-shell` drives MATLAB via the headless Engine API ([ADR-0001](adr/0001-use-matlab-engine-api.md)) without a console stdin stream:
- `keyboard`: Blocked upfront when entered directly at the prompt or via `-c` so it cannot hang the terminal. Use `disp`/`fprintf` or inspect variables directly in the **Session**.
- `input()`: Produces a clear error explaining the limitation. Pass parameters as function arguments or assign variables in the **Workspace** instead.

### MATLAB Not Found or Unsupported Release

- Ensure **MATLAB R2024a or newer** is installed.
- If MATLAB is installed in a non-standard directory not on `PATH`, set `--matlab-root`, `MATLAB_SHELL_ROOT`, or `config.toml` to the root folder containing `bin/<arch>` and `extern/engines/python`.

### Why doesn't `clc` inside a `.m` script clear my terminal?

Standalone `clc` at the interactive prompt is handled locally by `matlab-shell`, whereas `.m` scripts and compound lines (`a = 1; clc`) are forwarded directly to the MATLAB Engine, where `clc` produces no terminal output (see [ADR-0003](adr/0003-intercept-minimal-terminal-commands.md)).

### Suppressing Figure Windows

Use `msh --no-figure` or set `no_figure = true` in `config.toml`. When disabled in config, pass `msh --figure` to re-enable Figure windows for a single run.
