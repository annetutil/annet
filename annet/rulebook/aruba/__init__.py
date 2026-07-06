from collections import OrderedDict
from collections.abc import Iterator
from typing import Any

from annet.annlib.rulebook import common
from annet.annlib.rulebook.common import DiffItem
from annet.annlib.types import Op


def default_diff(
    old: OrderedDict[str, Any],
    new: OrderedDict[str, Any],
    diff_pre: OrderedDict[str, Any],
    _pops: tuple[str, ...] = (Op.AFFECTED,),
) -> list[DiffItem]:
    diff = common.base_diff(old, new, diff_pre, _pops, moved_to_affected=True)
    diff[:] = _skip_non_ap_env_affected(diff)
    return diff


def _skip_non_ap_env_affected(diff: list[DiffItem]) -> Iterator[DiffItem]:
    for x in diff:
        if x.op == Op.AFFECTED and not x.children:
            if x.diff_pre["attrs"]["context"].get("block") != "ap-env":
                continue
        yield x
