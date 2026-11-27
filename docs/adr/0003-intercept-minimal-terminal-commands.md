---
status: accepted
---

# Intercept Only Minimal Standalone Terminal Commands (exit, quit, clc)

Under the official MATLAB Engine API for Python ([ADR-0001](0001-use-matlab-engine-api.md)), MATLAB runs without a Desktop Command Window and does not expose UI events such as the private MVM `clc` event used by MathWorks' VS Code extension. Forwarding `clc` to the engine is a silent no-op, and forwarding `exit` or `quit` in a **Shared Session** would shut down an external MATLAB Desktop rather than detaching the terminal client. Therefore, `matlab-shell` intercepts only standalone top-level `exit`, `quit`, and `clc` (with optional trailing semicolon) at the interactive prompt.

## Considered Options

- **Minimal standalone allowlist (chosen)**: Intercept only standalone `exit`, `quit`, and `clc` at the prompt as **Intercepted Commands**. Both `clc` and `.clear` clear the visible screen and scrollback buffer via `\x1b[2J\x1b[3J\x1b[1;1H`, and `clc` in a **Shared Session** stays strictly terminal-local without altering the external MATLAB Desktop Command Window.
- **Pure passthrough (`.exit` and `.clear` only)**: Forces MATLAB users out of muscle-memory `clc` / `exit` / `quit` commands and risks accidentally closing a **Shared Session** via `exit`.
- **Rewriting compound statements or hooking private MVM events**: Fragile parsing of arbitrary MATLAB code or reliance on undocumented internal MATLAB interfaces rejected in [ADR-0001](0001-use-matlab-engine-api.md).

## Consequences

- All other MATLAB commands (`clear`, `whos`, `cd`, etc.), compound lines (such as `x = 1; clc`), and `.m` scripts are forwarded unmodified to the **Session**.
- `clc` inside `.m` scripts or compound statements remains a silent no-op under the headless engine; users expecting terminal clearing inside interactive sessions use standalone `clc` or `.clear`.
