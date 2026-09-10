"""Shared patch logic for comma-separated VLAN databases with dash ranges."""

import re
from collections.abc import Iterator
from typing import Any

from annet.annlib.lib import cisco_collapse_vlandb, cisco_expand_vlandb
from annet.annlib.types import Op


VLANDB_CHUNK = 15


def simple_ranges(
    rule: dict[str, Any], key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], **_: Any
) -> Iterator[tuple[bool, str, Any]]:
    """Patch a VLAN database, collapsing adjacent pairs into ranges.

    For example, ``1000,1001,1003`` becomes ``1000-1001,1003``.
    """
    yield from simple(rule, key, diff, tiny_ranges=True, exclude_added_blocks=False)


def simple_no_tiny_ranges(
    rule: dict[str, Any], key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], **_: Any
) -> Iterator[tuple[bool, str, Any]]:
    """Patch a VLAN database without folding two-ID runs inside larger lists.

    For example, ``1000,1001,1003`` stays ``1000,1001,1003``, while
    ``1000,1001,1002,1004`` becomes ``1000-1002,1004``.
    """
    yield from simple(rule, key, diff, tiny_ranges=False, exclude_added_blocks=False)


def simple(
    rule: dict[str, Any],
    key: tuple[str, ...],
    diff: dict[str, list[dict[str, Any]]],
    *,
    tiny_ranges: bool,
    exclude_added_blocks: bool,
) -> Iterator[tuple[bool, str, Any]]:
    """Patch one ordinary VLAN database by comparing expanded VLAN IDs."""
    # pylint: disable=unused-argument
    for affected in diff[Op.AFFECTED]:
        yield (True, affected["row"], affected["children"])

    (prefix, new, new_blocks) = parse_actions(diff[Op.ADDED])
    (prefix2, old, old_blocks) = parse_actions(diff[Op.REMOVED])
    if not prefix:
        prefix = prefix2

    for vlan_id in (set(old_blocks.keys()) - set(new_blocks)) & new:
        # The contents of the vlan block were removed, but the vlan itself is still there
        yield (True, "%s %s" % (prefix, vlan_id), old_blocks[vlan_id])

    removed = old.difference(new)
    added = new.difference(old)
    if exclude_added_blocks:
        # Catalysts do not list vlans in batch mode if they are represented as blocks
        added -= new_blocks.keys()

    if removed:
        collapsed = cisco_collapse_vlandb(removed, tiny_ranges)
        for chunk in iter_chunks(collapsed, VLANDB_CHUNK):
            yield (False, "no %s%s%s" % (prefix, " ", ",".join(chunk)), None)

    if added:
        collapsed = cisco_collapse_vlandb(added, tiny_ranges)
        for chunk in iter_chunks(collapsed, VLANDB_CHUNK):
            yield (True, "%s%s%s" % (prefix, " ", ",".join(chunk)), None)

    if new_blocks:
        for vlan_id, block in new_blocks.items():
            yield (True, "%s %s" % (prefix, vlan_id), block)


def iter_chunks(items: list[str], size: int) -> Iterator[list[str]]:
    for offset in range(0, len(items), size):
        yield items[offset : offset + size]


def parse_actions(actions: list[dict[str, Any]]) -> tuple[str | None, set[int], dict[int, Any]]:
    prefix = None
    vlandb: set[int] = set()
    blocks: dict[int, Any] = {}
    for action in actions:
        (prefix, part) = parse_row(action["row"])
        if action["children"]:
            assert len(part) == 1, "vlandb block must contain one and only one vlanid: %s" % action["row"]
            blocks[list(part)[0]] = action["children"]
        vlandb.update(part)
    return (prefix, vlandb, blocks)


def parse_row(row: str) -> tuple[str, set[int]]:
    # sometimes ciscos put spaces between vlan ranges, and sometimes they do not.
    words = re.sub(r",\s+", ",", row).split()

    if words[-1] == "none":
        # switchport trunk allowed vlan none
        return (" ".join(words[:-1]), set())
    assert re.match(r"[\d,-]+$", words[-1]), "Unable to parse vlancfg row: %s" % row
    prefix = " ".join(words[:-2] if words[-2] == "add" else words[:-1])
    vlancfg = words[-1]
    vlandb = cisco_expand_vlandb(vlancfg)
    return (prefix, vlandb)
