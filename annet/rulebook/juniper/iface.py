import ipaddress
from collections import OrderedDict as odict
from typing import Any

from annet.annlib.types import Op
from annet.rulebook import common
from annet.rulebook.common import DiffItem


def ipv6_addr(
    old: odict[str, Any], new: odict[str, Any], diff_pre: odict[str, Any], _pops: tuple[str, ...]
) -> list[DiffItem]:
    """
    Convert all the ipv6 addresses into IPv6Interface objects and compare them afterwards
    """
    address_new_line = [a for a in map(_parse_ipv6, new) if a]
    address_old_line = [a for a in map(_parse_ipv6, old) if a]

    ret = []
    for item in common.default_diff(old, new, diff_pre, _pops):
        # Check whether an address marked for removal is present in the new list
        if item.op == Op.REMOVED and _parse_ipv6(item.row) in address_new_line:
            result_item = DiffItem(Op.AFFECTED, item.row, item.children, item.diff_pre)
        # Check whether an address marked for addition is present in the old list
        elif item.op == Op.ADDED and _parse_ipv6(item.row) in address_old_line:
            result_item = None
        # Everything else is left unchanged
        else:
            result_item = item
        if result_item:
            ret.append(result_item)
    return ret


def _parse_ipv6(row: str) -> ipaddress.IPv6Interface | None:
    """
    Parses an IPv6 interface out of a row assuming that the address comes second.
    Returns an IPv6Interface object or None.
    """
    if row:
        parts = row.split()
        if len(parts) > 1:
            return ipaddress.IPv6Interface(parts[1])
    return None
