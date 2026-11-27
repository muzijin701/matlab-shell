"""Command-line interface entrypoint for matlab-shell / msh."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TextIO

from matlab_shell import __version__
from matlab_shell.backend import RealSessionBackend, SessionBackend
from matlab_shell.config import load_config
from matlab_shell.discovery import discover_matlab
from matlab_shell.errors import MatlabShellError
from matlab_shell.paths import get_history_path
from matlab_shell.repl import PromptDriver, run_repl
from matlab_shell.runner import run_oneshot


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="matlab-shell",
        description="Interactive terminal MATLAB CLI",
    )
    parser.add_argument(
        "script",
        nargs="?",
        help="Path to a .m script file for One-Shot Execution",
    )
    parser.add_argument(
        "-c",
        "--command",
        dest="command",
        help="Evaluate a single MATLAB expression or statement and exit",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Enter interactive >> prompt after running a script or command",
    )
    parser.add_argument(
        "--attach",
        nargs="?",
        const="",
        default=None,
        metavar="NAME",
        help="Attach to an existing Shared Session (optionally by name)",
    )
    parser.add_argument(
        "--cd",
        action="store_true",
        dest="sync_cd",
        help="Sync MATLAB working directory to terminal CWD when attaching to a Shared Session",
    )
    parser.add_argument(
        "--matlab-root",
        dest="matlab_root",
        help="Explicit path to local MATLAB installation root",
    )
    parser.add_argument(
        "--no-figure",
        action="store_true",
        help="Disable native MATLAB Figure windows for the Session",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    backend: SessionBackend | None = None,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    which: Callable[[str], str | None] | None = None,
    default_candidates: Sequence[Path] | None = None,
    registry_candidates: Sequence[Path] | None = None,
    prompt_driver: PromptDriver | None = None,
    history_path: Path | None = None,
    config_path: Path | None = None,
    clear_screen: Callable[[], None] | None = None,
) -> int:
    """Parse CLI arguments, resolve config & MATLAB, and run REPL or One-Shot Execution."""
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    working_dir = Path.cwd() if cwd is None else cwd
    env_map = os.environ if env is None else env

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command is not None and args.script is not None:
        err.write("Error: Cannot specify both -c/--command and a script file.\n")
        err.flush()
        return 2

    script_path: Path | None = None
    if args.script is not None:
        candidate = Path(args.script)
        script_path = candidate if candidate.is_absolute() else working_dir / candidate
        if not script_path.exists():
            err.write(f"Error: Script file not found: {script_path}\n")
            err.flush()
            return 2
        if script_path.is_dir():
            err.write(f"Error: Expected a .m script file, got directory: {script_path}\n")
            err.flush()
            return 2

    try:
        config = load_config(config_path=config_path, env=env_map)
        installation = discover_matlab(
            cli_root=args.matlab_root,
            env=env_map,
            config_root=config.matlab_root,
            which=which,
            default_candidates=default_candidates,
            registry_candidates=registry_candidates,
        )
        effective_no_figure = bool(args.no_figure or config.no_figure)
        active_backend = RealSessionBackend() if backend is None else backend

        if (args.command is None and script_path is None) or args.interactive:
            resolved_history = (
                get_history_path(env=env_map) if history_path is None else history_path
            )
            return run_repl(
                backend=active_backend,
                installation=installation,
                cwd=working_dir,
                stdout=out,
                stderr=err,
                history_path=resolved_history,
                prompt_driver=prompt_driver,
                initial_command=args.command,
                initial_script=script_path,
                no_figure=effective_no_figure,
                attach_name=args.attach,
                sync_cwd_on_attach=args.sync_cd,
                editing_mode=config.editing_mode,
                clear_screen=clear_screen,
            )

        return run_oneshot(
            backend=active_backend,
            installation=installation,
            cwd=working_dir,
            stdout=out,
            stderr=err,
            command=args.command,
            script=script_path,
            no_figure=effective_no_figure,
            attach_name=args.attach,
            sync_cwd_on_attach=args.sync_cd,
        )
    except MatlabShellError as exc:
        err.write(f"Error: {exc}\n")
        err.flush()
        return 1


def main() -> None:
    """Console script entry point for `matlab-shell` and `msh`."""
    sys.exit(run_cli())
