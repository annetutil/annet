import argparse
import os
import platform
import shutil
import subprocess
from typing import Any

import yaml
from valkit.python import valid_logging_level

from annet import api, cli_args, filtering, generators
from annet.argparse import ArgParser, subcommand
from annet.lib import get_context_path, repair_context_file


def fill_base_args(parser: ArgParser, pkg_name: str, logging_config: str) -> None:
    parser.add_argument(
        "--log-level",
        default="WARN",
        type=valid_logging_level,
        help="Уровень детализации логов (DEBUG, DEBUG2 (with transport debug), INFO, WARN, CRITICAL)",
    )
    parser.add_argument("--pkg_name", default=pkg_name, help=argparse.SUPPRESS)
    parser.add_argument("--logging_config", default=logging_config, help=argparse.SUPPRESS)


def list_subcommands() -> dict[str, Any]:
    return globals().copy()


@subcommand(is_group=True)
def context() -> None:
    """A group of commands for manipulating context.

    By default, the context file is located in '~/.annet/context.yml',
    but it can be set with the ANN_CONTEXT_CONFIG_PATH environment variable.
    """
    context_touch()


@subcommand(parent=context)
def context_touch() -> None:
    """Show the context file path, and if the file is not present, create it with the default configuration"""
    print(get_context_path(touch=True))


@subcommand(cli_args.SelectContext, parent=context)
def context_set_context(args: cli_args.SelectContext) -> None:
    """Set the current active context.

    The selected context is used by default unless the environment variable ANN_SELECTED_CONTEXT is set
    """
    with open(path := get_context_path(touch=True)) as f:
        data = yaml.safe_load(f)
    if args.context_name not in data.get("context", {}):
        raise KeyError(
            f"Cannot select context with name '{args.context_name}'. "
            f"Available options are: {list(data.get('context', []))}"
        )
    data["selected_context"] = args.context_name
    with open(path, "w") as f:
        yaml.dump(data, f, sort_keys=False)


@subcommand(parent=context)
def context_edit() -> None:
    """Open the context file using an editor from the EDITOR environment variable.

    If the EDITOR variable is not set, default variables are: "notepad.exe" for Windows and "vi" otherwise
    """
    if e := os.getenv("EDITOR"):
        editor = e
    elif platform.system() == "Windows":
        editor = "notepad.exe"
    elif shutil.which("vim"):
        editor = "vim"
    else:
        editor = "vi"
    path = get_context_path(touch=True)
    proc = subprocess.Popen([editor, path])
    proc.wait()


@subcommand(parent=context)
def context_repair() -> None:
    """Try to fix the context file's structure if it was generated for the older versions of annet"""
    repair_context_file()
