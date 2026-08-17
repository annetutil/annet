from typing import Any

from annet.annlib.types import Op
from annet.rulebook import common


def remove_last_param(
    rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any
) -> common.LogicResult:
    if diff[Op.REMOVED]:
        for rem in diff[Op.REMOVED]:
            # Handle the removal of the last parameter of the command
            cmd_parts = rem["row"].split(" ")
            cmd_parts.remove(cmd_parts[len(cmd_parts) - 1])
            yield False, "undo %s" % " ".join(cmd_parts), None
    else:
        yield from common.default(rule, key, diff)
