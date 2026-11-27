# matlab-shell

An interactive terminal shell for driving a local MATLAB installation directly from a system console without launching the MATLAB Desktop GUI.

## Language

**Session**:
A running MATLAB execution environment bound to a `matlab-shell` invocation, owning a **Workspace** and a current working directory.
_Avoid_: Engine, instance, process, kernel

**Managed Session**:
A **Session** created by `matlab-shell` on startup and automatically shut down when `matlab-shell` exits.
_Avoid_: Private session, standalone session, ephemeral session

**Shared Session**:
An externally started MATLAB **Session** published for attachment; `matlab-shell` connects to it on demand and detaches without shutting it down on exit.
_Avoid_: Remote session, daemon, persistent session

**Workspace**:
The in-memory variable state preserved across commands within a **Session**.
_Avoid_: Scope, environment, memory

**One-Shot Execution**:
Running a single `.m` script file or inline MATLAB expression directly from the command line and exiting upon completion, without entering the interactive prompt.
_Avoid_: Batch mode, headless run, script mode

**Meta-Command**:
A `.`-prefixed control command entered at the interactive prompt to manage `matlab-shell` or inspect the active **Session**, rather than being evaluated as MATLAB code.
_Avoid_: Slash command, magic command, builtin
