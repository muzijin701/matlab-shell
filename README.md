[English](README.en.md)

# matlab-shell (`msh`)

基于 `uv` + Python 的终端交互式 MATLAB CLI 工具，让你直接在 Windows Terminal、macOS Terminal 或 Linux Shell 中获得 `>>` 交互式体验与脚本单次执行能力，无需打开完整的 MATLAB Desktop 桌面。

## 环境要求

- 本地已安装并激活 **MATLAB R2024a 或更高版本**（当前已在 MATLAB R2026a 验证通过）
- 源码/开发运行需要 Python **3.12**（`>=3.12,<3.14`）与 [`uv`](https://docs.astral.sh/uv/)；独立安装包内置运行时，无需单独安装 Python

## 安装方式

### 1. 包管理器（推荐）

- **Windows (Scoop)**：
  ```powershell
  scoop bucket add muzijin701 https://github.com/muzijin701/scoop-bucket
  scoop install muzijin701/matlab-shell
  ```
- **macOS / Linux (Homebrew)**：
  ```sh
  brew tap muzijin701/tap
  brew install matlab-shell
  ```

### 2. 一键安装脚本

- **Windows (PowerShell)**：
  ```powershell
  irm https://raw.githubusercontent.com/muzijin701/matlab-shell/main/install.ps1 | iex
  ```
- **macOS / Linux**：
  ```sh
  curl -fsSL https://raw.githubusercontent.com/muzijin701/matlab-shell/main/install.sh | sh
  ```

### 3. GitHub Releases 独立压缩包

从 [Releases](https://github.com/muzijin701/matlab-shell/releases) 下载对应平台压缩包并解压，将解压目录加入 `PATH` 即可直接使用 `msh` / `matlab-shell`。

### 4. Python 工具链安装

```powershell
uv tool install --python 3.12 git+https://github.com/muzijin701/matlab-shell.git
# 或使用 pipx / pip
pipx install --python 3.12 git+https://github.com/muzijin701/matlab-shell.git
```

## 常用用法

```powershell
# 进入交互式 >> 提示符（自动启动 Managed Session 并同步当前目录）
msh

# 单次执行（One-Shot Execution），适合脚本或管道重定向
msh demo.m
msh -c "disp(1 + 1)"

# 执行脚本后留在 >> 继续交互查看 Workspace
msh -i demo.m

# 接入已打开的 Shared Session（需先在 MATLAB 执行 matlab.engine.shareEngine）
msh --attach
msh --attach MySession --cd

# 指定 MATLAB 根目录 / 禁用原生 Figure 窗口
msh --matlab-root "D:\software\winget-apps" --no-figure
```

### 交互模式功能

- **多行自动续行**：括号未闭合、行尾 `...`、未配对代码块（`if`/`for`/`while`/`switch`/`try`/`function`/`classdef` 缺 `end`）自动续行（`... `），支持 `Alt+Enter` 手动换行。
- **分层 Tab 补全**：`.` 开头补全 Meta-Command；引号内或 `!` 后补全本地路径；代码区补全当前 Workspace 变量、本地 `.m` 文件名与常用关键字。
- **Meta-Command**：`.help`、`.sessions`、`.attach [name]`、`.vars`、`.clear`、`.info`、`.exit`。
- **历史与中断**：跨会话命令历史（`↑` / `Ctrl+R`）；计算中 `Ctrl+C` 尝试取消当前任务，空闲 `Ctrl+C` 清空输入，`Ctrl+D` 或 `exit` 退出/断开。

## 可选配置文件（`config.toml`）

零配置即可开箱使用。如需固化偏好，可在用户配置目录创建 `config.toml`（Windows：`%APPDATA%\matlab-shell\config.toml`；macOS：`~/Library/Application Support/matlab-shell/config.toml`；Linux：`~/.config/matlab-shell/config.toml`）：

```toml
matlab_root = "D:\\software\\winget-apps"
editing_mode = "emacs" # 或 "vi"
no_figure = false
```

发现优先级：`--matlab-root` > `MATLAB_SHELL_ROOT` / `MATLAB_ROOT` > `config.toml` > `PATH` > 系统默认安装目录 / Windows 注册表。

## 本地开发与构建

```powershell
uv sync
uv run pytest -m "not matlab" -v
uv run pytest -m matlab -v           # 需要本机安装 MATLAB R2024a+
uv run python scripts/build_release.py
```

## 协作约定

- 术语与架构决策见 [`GLOSSARY.md`](GLOSSARY.md) 与 `docs/adr/`。
- Issue 与规格跟踪约定见 [`AGENTS.md`](AGENTS.md) 与 `docs/agents/`。
