[中文](README.md)

# matlab-shell

An interactive terminal MATLAB CLI built with `uv` and Python (project skeleton and engineering workflow initialized; architecture and CLI design pending discussion).

## Prerequisites

- A local licensed MATLAB installation (target environment: **MATLAB R2026a / `26.1`**, matching `matlabengine==26.1.*`)
- Python **3.12** (`matlabengine` `26.1` supports Python 3.9–3.13)
- [`uv`](https://docs.astral.sh/uv/)

## Quick Check

```powershell
uv run matlab-shell
```

## Project Conventions

- Issues and specs are tracked in GitHub Issues; see [`AGENTS.md`](AGENTS.md) and `docs/agents/`.
