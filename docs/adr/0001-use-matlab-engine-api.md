---
status: accepted
---

# Use Official MATLAB Engine API for Python as Backend

On Windows, `matlab -nodesktop` opens a separate Command Window GUI instead of attaching interactively to Windows Terminal, so `matlab-shell` drives MATLAB through the official `matlabengine` Python API (`start_matlab` / `connect_matlab`).

## Considered Options

- **Official `matlabengine` Python API (chosen)**: Supported by MathWorks across platforms, streams `stdout`/`stderr` directly into the terminal, and natively supports both managed and shared sessions.
- **Wrapping `matlab -nodesktop` over PTY**: Works on Linux/macOS, but cannot embed interactively in Windows Terminal.
- **Reusing the VS Code MATLAB extension's internal connector**: Relies on undocumented private interfaces tied to MATLAB internals and is fragile across MATLAB releases.

## Consequences

- Interactive MATLAB stdin calls (`input()`, `keyboard`) are not supported because the engine runs without a console stdin stream.
- The runtime Python version must remain within the target MATLAB release's supported range (e.g. Python 3.9–3.13 for MATLAB R2026a).
