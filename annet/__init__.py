import logging
import logging.config
import os
import pkgutil
import sys
from argparse import SUPPRESS, Namespace

import colorama
import yaml
from annet.annlib.errors import (  # pylint: disable=wrong-import-position
    DeployCancelled,
    ExecError,
)
from contextlog import patch_logging, patch_threading
from valkit.python import valid_logging_level

import annet.argparse


__all__ = ("DeployCancelled", "ExecError")

DEBUG2_LEVELV_NUM = 9


def fill_base_args(parser: annet.argparse.ArgParser, pkg_name: str, logging_config: str):
    parser.add_argument("--log-level", default="WARN", type=valid_logging_level,
                        help="Уровень детализации логов (DEBUG, DEBUG2 (with comocutor debug), INFO, WARN, CRITICAL)")
    parser.add_argument("--pkg_name", default=pkg_name, help=SUPPRESS)
    parser.add_argument("--logging_config", default=logging_config, help=SUPPRESS)


def init_logging(options: Namespace):
    patch_logging()
    patch_threading()
    logging.captureWarnings(True)
    logging_config = yaml.safe_load(pkgutil.get_data(options.pkg_name, options.logging_config))
    if options.log_level is not None:
        logging_config.setdefault("root", {})
        logging_config["root"]["level"] = options.log_level
    logging.addLevelName(DEBUG2_LEVELV_NUM, "DEBUG2")
    logging.config.dictConfig(logging_config)


def init(options: Namespace):
    init_logging(options)

    # Отключить colorama.init, если стоит env-переменная. Нужно в тестах
    if os.environ.get("ANN_FORCE_COLOR", None) not in [None, "", "0", "no"]:
        colorama.init = lambda *_, **__: None
    colorama.init()

    # Workaround for Python 3.8.0: https://bugs.python.org/issue38529
    import asyncio.streams
    if hasattr(asyncio.streams.StreamReaderProtocol, "_on_reader_gc"):
        asyncio.streams.StreamReaderProtocol._on_reader_gc = lambda *args, **kwargs: None  # pylint: disable=protected-access


def assert_python_version():
    if sys.version_info < (3, 9, 0):
        sys.stderr.write("Error: you need python 3.9.0 or higher\n")
        sys.exit(1)
