from __future__ import annotations

import asyncio
import os
import shutil
import sys
import threading
from collections.abc import Coroutine
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar, cast

import yaml
from contextlog import get_logger

from annet.annlib.lib import (  # pylint: disable=unused-import
    ContextOrderedDict as ContextOrderedDict,
)
from annet.annlib.lib import (
    HuaweiNumBlock as HuaweiNumBlock,
)
from annet.annlib.lib import (
    LMSMatcher as LMSMatcher,
)
from annet.annlib.lib import (
    add_annotation as add_annotation,
)
from annet.annlib.lib import (
    catch_ctrl_c as catch_ctrl_c,
)
from annet.annlib.lib import (
    cisco_collapse_vlandb as cisco_collapse_vlandb,
)
from annet.annlib.lib import (
    cisco_expand_vlandb as cisco_expand_vlandb,
)
from annet.annlib.lib import (
    find_exc_in_stack as find_exc_in_stack,
)
from annet.annlib.lib import (
    find_modules as find_modules,
)
from annet.annlib.lib import (
    first as first,
)
from annet.annlib.lib import (
    flatten as flatten,
)
from annet.annlib.lib import (
    huawei_collapse_vlandb as huawei_collapse_vlandb,
)
from annet.annlib.lib import (
    huawei_expand_vlandb as huawei_expand_vlandb,
)
from annet.annlib.lib import (
    huawei_iface_ranges as huawei_iface_ranges,
)
from annet.annlib.lib import (
    is_relative as is_relative,
)
from annet.annlib.lib import (
    jun_activate as jun_activate,
)
from annet.annlib.lib import (
    jun_is_inactive as jun_is_inactive,
)
from annet.annlib.lib import (
    juniper_fmt_prefix_lists_acl as juniper_fmt_prefix_lists_acl,
)
from annet.annlib.lib import (
    juniper_port_split as juniper_port_split,
)
from annet.annlib.lib import (
    make_ip4_mask as make_ip4_mask,
)
from annet.annlib.lib import (
    mako_render as mako_render,
)
from annet.annlib.lib import (
    merge_dicts as merge_dicts,
)
from annet.annlib.lib import (
    percentile as percentile,
)
from annet.annlib.lib import (
    uniq as uniq,
)


_HOMEDIR_PATH: str | None = None  # defaults to ~/.annet
_TEMPLATE_CONTEXT_PATH: str | None = None  # defaults to annet/configs/context.yml
_DEFAULT_CONTEXT_PATH: str | None = None  # defaults to ~/.annet/context.yml


def get_homedir_path() -> str:
    if _HOMEDIR_PATH is None:
        set_homedir_path(os.path.expanduser("~/.annet/"))
    assert _HOMEDIR_PATH is not None
    return _HOMEDIR_PATH


def set_homedir_path(path: str) -> None:
    global _HOMEDIR_PATH  # pylint: disable=global-statement
    _HOMEDIR_PATH = path


def get_template_context_path() -> str:
    if _TEMPLATE_CONTEXT_PATH is None:
        annet_file = sys.modules["annet"].__file__
        assert annet_file is not None
        set_template_context_path(str(Path(annet_file).parent / "configs/context.yml"))
    assert _TEMPLATE_CONTEXT_PATH is not None
    return _TEMPLATE_CONTEXT_PATH


def set_template_context_path(path: str) -> None:
    global _TEMPLATE_CONTEXT_PATH  # pylint: disable=global-statement
    _TEMPLATE_CONTEXT_PATH = path


def get_default_context_path() -> str:
    if _DEFAULT_CONTEXT_PATH is None:
        set_default_context_path("~/.annet/context.yml")
    assert _DEFAULT_CONTEXT_PATH is not None
    return _DEFAULT_CONTEXT_PATH


def set_default_context_path(path: str) -> None:
    global _DEFAULT_CONTEXT_PATH  # pylint: disable=global-statement
    _DEFAULT_CONTEXT_PATH = path


def get_default_log_dest() -> str:
    homedir = get_homedir_path()
    return os.path.join(homedir, "deploy/")


@lru_cache(maxsize=1)
def _get_template_context() -> dict[str, Any]:
    with open(get_template_context_path()) as f:
        return cast(dict[str, Any], yaml.safe_load(f))


def get_context_path(touch: bool = False) -> str:
    path = Path(os.getenv("ANN_CONTEXT_CONFIG_PATH", get_default_context_path())).expanduser().absolute()
    if not path.exists():
        src = get_template_context_path()
        if not touch:
            return str(src)
        try:
            # populate path with default configuration
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, path)
        except shutil.SameFileError:
            pass
    return str(path)


@lru_cache(maxsize=1)
def get_context() -> dict[str, Any]:
    with open(get_context_path()) as f:
        raw = yaml.safe_load(f)
    _fill_in_default_generator_modules(raw)
    context_name = os.getenv("ANN_SELECTED_CONTEXT", raw["selected_context"])
    res = {k: raw[k][v] for k, v in raw["context"][context_name].items()}
    if "ANN_GENERATORS_CONTEXT" in os.environ:  # an undocumented hack to maintain backwards compatibility; TODO: remove
        res["generators"] = raw["generators"][os.getenv("ANN_GENERATORS_CONTEXT")]
    return res


@lru_cache(maxsize=1)
def _warn_no_generators_in_context() -> None:
    get_logger().warning(
        "Older version of the context configuration found. Getting generators references from the template context"
    )


def _fill_in_default_generator_modules(raw: dict[str, Any]) -> bool:
    """Backwards compatibility hack to add existing generators refs to context"""
    if "generators" not in raw:
        _warn_no_generators_in_context()
        raw["generators"] = _get_template_context()["generators"]
        for dst_context in raw["context"].values():
            dst_context["generators"] = "default"
        return True
    return False


def repair_context_file() -> None:
    path = get_context_path()
    with open(path) as f:
        data = yaml.safe_load(f)
    if _fill_in_default_generator_modules(data):
        with open(path, "w") as f:
            yaml.dump(data, f, sort_keys=False)


ReturnType = TypeVar("ReturnType")


def do_async(coro: Coroutine[Any, Any, ReturnType], new_thread: bool = False) -> ReturnType:
    if new_thread:
        # start the new thread with the new event loop
        res: ReturnType | BaseException | None = None

        def wrapper(main: Coroutine[Any, Any, ReturnType]) -> None:
            nonlocal res
            try:
                res = asyncio.run(main)
            except BaseException as e:
                res = e

        thread = threading.Thread(target=wrapper, args=(coro,))
        thread.start()
        thread.join()
        if isinstance(res, BaseException):
            raise res
        return cast(ReturnType, res)
    else:
        return asyncio.run(coro)
