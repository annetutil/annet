from typing import Any

from annet.annlib.rulebook import common
from annet.annlib.types import Op


def syslog_level(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any) -> common.LogicResult:
    # syslog-level can be overwritten only
    if diff[Op.ADDED]:
        yield from common.default(rule, key, diff)
