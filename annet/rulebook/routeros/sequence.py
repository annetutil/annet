from collections.abc import Iterator
from typing import Any

from annet.annlib.types import Op


def erase_before(
    key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], **kwargs: Any
) -> Iterator[tuple[bool, str, None]]:
    """
    Handle RouterOS IP firewall and queue operations.
    """

    if diff[Op.MOVED] or diff[Op.ADDED] or diff[Op.REMOVED]:
        # Remove all rules
        yield False, "remove dynamic=no", None
    # Then the rules will be recreated in a new order
    for cmd in list(diff[Op.ADDED] + diff[Op.MOVED] + diff[Op.UNCHANGED]):
        yield True, cmd["row"], None
