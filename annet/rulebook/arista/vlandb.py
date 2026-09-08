"""VLAN database patch logic for Arista EOS.

EOS groups VLANs with identical configuration under one ranged header,
so every VLAN ID belongs to exactly one block::

    vlan 1000-1001,1004
       name foo
    vlan 1002-1003
       name bar

A ranged header accepts the same child commands as a single VLAN, applying
them to every VLAN in the range.
"""

from collections import OrderedDict
from collections.abc import Iterator
from typing import Any

from annet.annlib.lib import cisco_collapse_vlandb
from annet.annlib.types import Op
from annet.rulebook.generic.vlandb import VLANDB_CHUNK, iter_chunks, parse_row


_Signature = tuple[tuple[str, Any], ...]


def simple(
    rule: dict[str, Any], key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], **_: Any
) -> Iterator[tuple[bool, str, Any]]:
    # pylint: disable=unused-argument
    for affected in diff[Op.AFFECTED]:
        # The header is unchanged, so its children apply to the whole range
        yield (True, affected["row"], affected["children"])

    (prefix, old) = _parse_blocks(diff[Op.REMOVED])
    (prefix2, new) = _parse_blocks(diff[Op.ADDED])
    if not prefix:
        prefix = prefix2

    removed = old.keys() - new.keys()
    if removed:
        for chunk in iter_chunks(cisco_collapse_vlandb(removed), VLANDB_CHUNK):
            yield (False, "no %s %s" % (prefix, ",".join(chunk)), None)

    # VLANs going through the same config transition are patched together
    groups: dict[tuple[_Signature | None, _Signature], list[int]] = {}
    groups_children: dict[tuple[_Signature | None, _Signature], OrderedDict[str, Any]] = {}
    for vlan_id in sorted(new):
        old_children = old.get(vlan_id)
        old_signature = None if old_children is None else _signature(old_children)
        new_signature = _signature(new[vlan_id])
        if old_signature == new_signature:
            # The VLAN just moved to another ranged header
            continue
        transition = (old_signature, new_signature)
        if transition not in groups:
            groups[transition] = []
            groups_children[transition] = _merge_children(old_children or OrderedDict(), new[vlan_id])
        groups[transition].append(vlan_id)

    for transition, vlan_ids in groups.items():
        children = groups_children[transition] or None
        for chunk in iter_chunks(cisco_collapse_vlandb(vlan_ids), VLANDB_CHUNK):
            yield (True, "%s %s" % (prefix, ",".join(chunk)), children)


def _parse_blocks(actions: list[dict[str, Any]]) -> tuple[str | None, dict[int, OrderedDict[str, Any]]]:
    prefix = None
    blocks: dict[int, OrderedDict[str, Any]] = {}
    for action in actions:
        (prefix, vlan_ids) = parse_row(action["row"])
        for vlan_id in vlan_ids:
            blocks[vlan_id] = action["children"]
    return (prefix, blocks)


def _signature(children: OrderedDict[str, Any]) -> _Signature:
    """Return a comparable representation of a block's rows, ignoring diff ops."""
    rows = []
    for entry in children.values():
        for ops in entry["items"].values():
            for items in ops.values():
                for item in items:
                    rows.append((item["row"], _signature(item["children"])))
    return tuple(sorted(rows))


def _merge_children(old: OrderedDict[str, Any], new: OrderedDict[str, Any]) -> OrderedDict[str, Any]:
    """Combine the removed old block and the added new block into one block diff.

    Rows present in both blocks are dropped, so only the actual changes remain.
    """
    old_rows = set(_signature(old))
    new_rows = set(_signature(new))
    merged: OrderedDict[str, Any] = OrderedDict()
    for children, unchanged in ((old, new_rows), (new, old_rows)):
        for raw_rule, entry in children.items():
            for rule_key, ops in entry["items"].items():
                for op, items in ops.items():
                    for item in items:
                        if (item["row"], _signature(item["children"])) in unchanged:
                            continue
                        merged_entry = merged.setdefault(
                            raw_rule,
                            {"rule": entry["rule"], "attrs": entry["attrs"], "items": OrderedDict(), "positions": {}},
                        )
                        if rule_key not in merged_entry["items"]:
                            merged_entry["items"][rule_key] = {
                                Op.ADDED: [],
                                Op.REMOVED: [],
                                Op.MOVED: [],
                                Op.AFFECTED: [],
                                Op.UNCHANGED: [],
                            }
                            merged_entry["positions"][rule_key] = entry["positions"][rule_key]
                        merged_entry["items"][rule_key][op].append(item)
    return merged
