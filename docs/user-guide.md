[English](user-guide.en.md)

# matlab-shell (`msh`) 用户使用指南

`matlab-shell`（命令简写 `msh`）是一个在终端中直接驱动本地 MATLAB 安装的交互式 CLI 工具，适用于 Windows Terminal、macOS Terminal 和 Linux Shell，无需启动完整的 MATLAB Desktop 图形界面即可进行日常计算、脚本运行与工作区调试。

---

## 1. 环境要求与安装

### 环境要求

- 本地已安装并激活 **MATLAB R2024a 或更高版本**（已在 MATLAB R2026a 验证）。
- 仅运行独立安装包时**无需预先安装 Python 或 `uv`**（预编译包内置 Python 3.12 运行时）。
- 若使用源码或 `uv tool` / `pipx` 安装，需要 Python **3.12**（`>=3.12,<3.14`）。

### 预编译包覆盖平台

GitHub Releases 当前提供以下平台的开箱即用独立压缩包：

- `windows-x86_64`（`.zip`）
- `linux-x86_64`（`.tar.gz`）
- `macos-arm64`（Apple Silicon，`.tar.gz`）

其他架构（如 Intel macOS `x86_64` 或 Linux `arm64`）请通过第 4 种方式（`uv tool` / `pipx` + Python 3.12）安装。

### 安装方式

1. **包管理器（推荐）**：
   - Windows (Scoop)：
     ```powershell
     scoop bucket add muzijin701 https://github.com/muzijin701/scoop-bucket
     scoop install muzijin701/matlab-shell
     ```
   - macOS / Linux (Homebrew)：
     ```sh
     brew tap muzijin701/tap
     brew install matlab-shell
     ```

2. **一键安装脚本**（自动校验 Release `SHA256SUMS.txt`）：
   - Windows (PowerShell)：
     ```powershell
     irm https://raw.githubusercontent.com/muzijin701/matlab-shell/main/install.ps1 | iex
     ```
   - macOS / Linux：
     ```sh
     curl -fsSL https://raw.githubusercontent.com/muzijin701/matlab-shell/main/install.sh | sh
     ```

   > **自定义安装目录安全提示**：默认安装到独立子目录（Windows 为 `%LOCALAPPDATA%\matlab-shell\bin`，Unix 为 `~/.local/share/matlab-shell/bin`）。若通过 `MATLAB_SHELL_INSTALL_DIR` 指定目录，该目录必须是空目录或仅含旧版 `matlab-shell` 文件；如包含其他无关文件，安装脚本会拒绝覆盖并报错退出，避免误删。

3. **GitHub Releases 手动解压**：从 [Releases](https://github.com/muzijin701/matlab-shell/releases) 下载对应压缩包并解压，将目录加入 `PATH`。

4. **Python 工具链**：
   ```powershell
   uv tool install --python 3.12 git+https://github.com/muzijin701/matlab-shell.git
   # 或
   pipx install --python 3.12 git+https://github.com/muzijin701/matlab-shell.git
   ```

验证安装：

```powershell
msh --version
```

---

## 2. 启动模式与常用命令

| 场景 | 命令示例 | 说明 |
|---|---|---|
| 进入交互模式 | `msh` | 启动一个 **Managed Session** 并自动切换到当前终端目录 |
| 执行脚本（单次执行） | `msh demo.m` | 运行脚本后自动退出；输出写入 `stdout`，启动提示/错误写入 `stderr` |
| 执行单行表达式（单次执行） | `msh -c "disp(1 + 1)"` | 适合脚本自动化、管道重定向（如 `msh -c "disp(pi)" > out.txt`） |
| 执行后继续交互 | `msh -i demo.m` 或 `msh -i -c "x = 1;"` | 执行完毕后保留 **Workspace** 并进入 `>>` 提示符 |
| 接入已打开的 MATLAB | `msh --attach` / `msh --attach MySession` | 连接外部 **Shared Session**，退出时仅断开不关闭 MATLAB |
| 临时指定 MATLAB 路径 | `msh --matlab-root "C:\Program Files\MATLAB\R2026a"` | 覆盖自动发现与环境变量 |
| 控制原生 Figure 窗口 | `msh --no-figure` / `msh --figure` | 禁用或强制开启原生图形窗口（可覆盖 `config.toml`） |

> 提示：`msh` 与 `matlab-shell` 为等价命令入口。

---

## 3. 交互模式功能详解

### 多行自动续行

在 `>>` 提示符输入代码并按 `Enter` 时，若检测到语句尚未闭合，会自动换行并切换为 `... ` 续行提示符：

- 未闭合的括号：`(...)`、`[...]`、`{...}`
- 行尾续行符：`...`（含后方行内注释 `... % note`）
- 未配对的代码块：`if`、`for`、`parfor`、`while`、`switch`、`try`、`function`、`classdef`、`spmd`（以及 `classdef` 内的 `properties`/`methods`/`events`/`enumeration`）缺少对应的 `end`

如需手动强制换行，可按 `Alt+Enter`。

### 分层 Tab 补全

按 `Tab` 键时，补全器在本地零延迟计算候选结果（不会阻塞 MATLAB 计算）：

1. **Meta-Command 层**：行首输入 `.`（如 `.s` + `Tab` → `.sessions`）。
2. **路径补全层**：处于单引号/双引号字符串内（如 `run('sub/`）或 `!` Shell 命令后，实时基于当前 **Session** 工作目录补全子目录与文件。
3. **代码符号层**：依次补全当前 **Workspace** 变量、当前 **Session** 目录下的 `.m` 脚本文件名以及常用 MATLAB 关键字。

在交互模式中执行 `cd` 切换目录后，Tab 补全与 `.info` 会自动同步到新的 **Session** 工作目录。

### Meta-Command 与 Intercepted Command

`matlab-shell` 将本地控制命令分为两类，其余全部 MATLAB 语句（如 `clear`、`whos`、`cd`、`plot`）均原样透传给 **Session**：

1. **Meta-Command（`.` 前缀控制命令）**

| 命令 | 说明 |
|---|---|
| `.help` | 显示内置控制命令与快捷键帮助 |
| `.sessions` | 列出当前可接入的 **Shared Session**（标记当前活跃会话） |
| `.attach [name]` | 切换到指定 **Shared Session**；不带名称且存在多个会话时弹出编号选择 |
| `.vars` | 查看当前 **Workspace** 变量摘要（等价于 `whos`） |
| `.clear` | 清空当前终端可视屏幕与滚动缓冲区（不动外部 MATLAB Desktop） |
| `.info` | 显示绑定的 MATLAB 根目录、版本、发现来源、Session 类型及实时 `Session CWD` |
| `.exit` | 退出 `matlab-shell`（若为 **Shared Session** 则仅断开连接） |

2. **Intercepted Command（本地拦截的独立 MATLAB 命令）**

在交互提示符下**单独输入**以下三个命令（可带末尾分号 `;`）时，由 `matlab-shell` 在终端侧直接处理，不会导致误关闭桌面或静默无效：

- `clc` / `clc;`：清空当前终端可视屏幕与滚动缓冲区（与 `.clear` 一致；在 **Shared Session** 下不会清空外部 MATLAB Desktop 窗口）。
- `exit` / `quit`（含带分号形式）：安全退出终端，或在 **Shared Session** 下仅断开连接而不关闭外部 MATLAB。

> 注意：包含多条语句的复合行（如 `x = 1; clc`）或 `.m` 脚本文件内部的 `clc` 仍会原样发往 MATLAB；在无桌面 Engine 下，脚本内的 `clc` 为空操作。

### Shell 命令、历史记录与快捷键

- **Shell 透传**：以 `!` 开头的行（如 `!git status`、`!dir`）直接透传给 MATLAB 执行并实时回显输出。
- **跨会话历史**：自动保存为纯文本文件，支持 `↑`/`↓` 与 `Ctrl+R` 增量搜索：
  - Windows：`%LOCALAPPDATA%\matlab-shell\history.txt`
  - macOS：`~/Library/Application Support/matlab-shell/history.txt`
  - Linux：`${XDG_DATA_HOME:-~/.local/share}/matlab-shell/history.txt`
- **中断与退出**：
  - 空闲时按 `Ctrl+C`：清空/取消当前输入行，不退出。
  - MATLAB 计算中按 `Ctrl+C`：向引擎发送异步取消请求。
  - 空行按 `Ctrl+D`：退出（或断开 **Shared Session**）。

---

## 4. 连接已打开的 MATLAB（Shared Session）

当你需要把计算结果保留在桌面 MATLAB 窗口，或借用已打开的 MATLAB 进程免去冷启动耗时，可使用 **Shared Session**：

1. 在桌面 MATLAB 的 Command Window 中执行一次共享命令（也可指定名称）：
   ```matlab
   matlab.engine.shareEngine
   % 或指定名称：
   matlab.engine.shareEngine('MySession')
   ```
2. 在终端接入：
   ```powershell
   msh --attach                 # 仅一个会话时直连；多个时弹出编号列表选择
   msh --attach MySession       # 按名称直接接入
   msh --attach MySession --cd  # 接入后把 MATLAB 工作目录同步到当前终端目录
   ```
3. 默认情况下，`--attach` 与 REPL 内的 `.attach` **不会改动外部 MATLAB 原有的工作目录**（除非显式传入 `--cd`）。
4. 退出或执行 `.exit` / `exit` / `Ctrl+D` 时，终端仅安全断开，外部 MATLAB Desktop 保持运行。

---

## 5. 可选配置与 MATLAB 发现机制

### `config.toml` 配置

零配置即可开箱使用。如需保存个人默认选项，可在以下路径创建 `config.toml`：

- Windows：`%APPDATA%\matlab-shell\config.toml`
- macOS：`~/Library/Application Support/matlab-shell/config.toml`
- Linux：`${XDG_CONFIG_HOME:-~/.config}/matlab-shell/config.toml`

支持字段（全部可选）：

```toml
# 显式指定 MATLAB 安装根目录
matlab_root = "C:\\Program Files\\MATLAB\\R2026a"

# 终端行编辑键位模式："emacs"（默认）或 "vi"
editing_mode = "emacs"

# 是否默认禁用原生 Figure 窗口（可在命令行用 --figure 临时覆盖）
no_figure = false
```

### MATLAB 安装发现优先级

`matlab-shell` 按以下 5 级顺序定位 **MATLAB R2024a+** 安装目录（若显式指定的路径无效或版本过旧，会直接报错而不会静默回退）：

1. 命令行参数 `--matlab-root <path>`
2. 环境变量 `MATLAB_SHELL_ROOT` → `MATLAB_ROOT`
3. 配置文件 `config.toml` 中的 `matlab_root`
4. `PATH` 中的 `matlab` 可执行文件反推根目录
5. 操作系统默认安装目录与 Windows 注册表（多个有效版本时自动选择最新版本）

---

## 6. 已知限制与常见问题排查

### Q1：为什么脚本或命令里的 `input()` 与 `keyboard` 不能交互？

`matlab-shell` 通过官方无桌面 MATLAB Engine API 运行（见 [ADR-0001](adr/0001-use-matlab-engine-api.md)），底层进程没有交互式标准输入流（stdin）：
- `keyboard`：直接输入时会被提前拦截并报错（避免阻塞终端）。建议改用日志输出（`disp` / `fprintf`）或直接在 **Managed/Shared Session** 中交互调试变量。
- `input()`：调用时会返回明确提示。建议把交互参数改为函数入参或提前在 **Workspace** 赋值变量。

### Q2：提示找不到 MATLAB 或版本不支持怎么办？

- 确认安装的是 **MATLAB R2024a 或更高版本**。
- 如果 MATLAB 安装在非默认路径（例如自定义盘符或 Scoop/Winget 目录）且不在 `PATH` 中，请通过 `--matlab-root`、`MATLAB_SHELL_ROOT` 或 `config.toml` 指定包含 `bin/<arch>` 与 `extern/engines/python` 的根目录。

### Q3：如果脚本中有 `clc`，为什么没有清屏？

在交互提示符下单独输入 `clc` 会由终端直接清屏；但写在 `.m` 脚本内部或复合语句（如 `a = 1; clc`）里的 `clc` 会原样交给无桌面 MATLAB 引擎执行，而无桌面引擎下 `clc` 本身不会向 `stdout` 输出任何终端控制序列（详见 [ADR-0003](adr/0003-intercept-minimal-terminal-commands.md)）。

### Q4：不想要大量 `plot()` 弹窗怎么办？

可在启动时传入 `--no-figure`，或在 `config.toml` 中设置 `no_figure = true`；之后若某次需要临时看图，可使用 `msh --figure` 覆盖。
