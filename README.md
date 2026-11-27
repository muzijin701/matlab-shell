[English](README.en.md)

# matlab-shell

基于 `uv` + Python 的终端交互式 MATLAB CLI 工具（项目骨架与工程协作配置已初始化，具体交互与架构方案待讨论确立）。

## 环境要求

- 本地已安装并激活 MATLAB（当前目标环境为 **MATLAB R2026a / `26.1`**，对应 `matlabengine==26.1.*`）
- Python **3.12**（`matlabengine` `26.1` 支持 Python 3.9–3.13）
- [`uv`](https://docs.astral.sh/uv/)

## 快速验证

```powershell
uv run matlab-shell
```

## 协作约定

- 仓库使用 GitHub Issues 跟踪任务与规格，相关配置见 [`AGENTS.md`](AGENTS.md) 与 `docs/agents/`。
