from collections.abc import Iterator
from typing import Any, cast

from annet.annlib.lib import huawei_collapse_vlandb as collapse_vlandb
from annet.annlib.lib import huawei_expand_vlandb as expand_vlandb
from annet.annlib.types import Op


_DEFAULT_VLAN_ID = 1


# =====
def single(
    rule: dict[str, Any], key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], **_: Any
) -> Iterator[tuple[bool, str, Any]]:
    yield from _process_vlandb(rule, key, diff, False, False, None)


def multi(
    rule: dict[str, Any], key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], **_: Any
) -> Iterator[tuple[bool, str, Any]]:
    yield from _process_vlandb(rule, key, diff, True, False, 10)


def multi_all(
    rule: dict[str, Any], key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], **_: Any
) -> Iterator[tuple[bool, str, Any]]:
    yield from _process_vlandb(rule, key, diff, True, True, 10)


def global_vlan(
    rule: dict[str, Any], key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], **_: Any
) -> Iterator[tuple[bool, str, Any]]:
    """Patch global VLAN declarations by ID while preserving VLAN blocks."""
    # Required callback arguments; this logic derives commands from diff alone.
    del rule, key
    for affected in diff[Op.AFFECTED]:
        if affected["children"]:
            yield (True, affected["row"], affected["children"])

    new, new_blocks = _parse_global_vlan_actions(diff[Op.ADDED])
    old, old_blocks = _parse_global_vlan_actions(diff[Op.REMOVED])

    for vlan_id in (old_blocks.keys() - new_blocks.keys()) & new:
        yield (True, f"vlan {vlan_id}", old_blocks[vlan_id])

    removed = old - new
    added = (new - old) - new_blocks.keys()
    # VLAN 1 is the system default and H3C does not allow it to be deleted.
    for vlan_id in sorted(removed - {_DEFAULT_VLAN_ID}):
        yield (False, f"undo vlan {vlan_id}", None)
    for vlan_id in sorted(added):
        yield (True, f"vlan {vlan_id}", None)

    for vlan_id, block in new_blocks.items():
        yield (True, f"vlan {vlan_id}", block)


# =====
def _process_vlandb(
    rule: dict[str, Any],
    key: tuple[str, ...],
    diff: dict[str, list[dict[str, Any]]],
    multi: bool,
    multi_all: bool,
    multi_chunk: int | None,
) -> Iterator[tuple[bool, str, None]]:
    assert len(diff[Op.AFFECTED]) == 0, "WTF? Affected signle: %r" % (diff[Op.AFFECTED])
    if not multi:
        for op in (Op.ADDED, Op.REMOVED):
            assert 0 <= len(diff[op]) <= 1, "Too many actions: %r" % (diff)

    if diff[Op.REMOVED] and not diff[Op.ADDED]:  # Removed
        if multi and multi_all:
            yield (False, rule["reverse"].format(*key) + " all", None)
            return
        elif not multi and not multi_all:
            yield (False, rule["reverse"].format(*key), None)
            return

    (prefix_add, new) = _parse_vlancfg_actions(diff[Op.ADDED])
    (prefix_del, old) = _parse_vlancfg_actions(diff[Op.REMOVED])
    removed = old.difference(new)
    added = new.difference(old)

    if removed:
        collapsed = collapse_vlandb(removed)
        # multi implies multi_chunk is not None (see single/multi/multi_all callers)
        for chunk in _chunked(collapsed, cast(int, multi_chunk)) if multi else [collapsed]:
            yield (False, "undo %s %s" % (prefix_del, " ".join(chunk)), None)

    if added:
        collapsed = collapse_vlandb(added)
        for chunk in _chunked(collapsed, cast(int, multi_chunk)) if multi else [collapsed]:
            yield (True, "%s %s" % (prefix_add, " ".join(chunk)), None)


def _chunked(items: list[str], size: int) -> Iterator[list[str]]:
    for offset in range(0, len(items), size):
        yield items[offset : offset + size]


def _parse_vlancfg_actions(actions: list[dict[str, Any]]) -> tuple[str | None, set[int]]:
    prefix = None
    vlandb: set[int] = set()
    for action in actions:
        (prefix, part) = _parse_vlancfg(action["row"])
        vlandb.update(part)
    return (prefix, vlandb)


def _parse_global_vlan_actions(actions: list[dict[str, Any]]) -> tuple[set[int], dict[int, Any]]:
    vlan_ids: set[int] = set()
    blocks: dict[int, Any] = {}
    for action in actions:
        prefix, row_ids = _parse_vlancfg(action["row"])
        assert prefix == "vlan", action["row"]
        if action["children"]:
            assert len(row_ids) == 1, f"VLAN block must contain one VLAN ID: {action['row']}"
            blocks[next(iter(row_ids))] = action["children"]
        vlan_ids.update(row_ids)
    return vlan_ids, blocks


def _parse_vlancfg(row: str) -> tuple[str, set[int]]:
    parts = row.split()
    assert len(parts) > 0, row
    index = 0  # parts is non-empty, so the loop below always reassigns index
    for index, item in reversed(list(enumerate(parts))):
        if not (item.isdigit() or item == "to"):
            break
    prefix = " ".join(parts[: index + 1])
    vlandb = expand_vlandb(" ".join(parts[index + 1 :]))
    return (prefix, vlandb)
