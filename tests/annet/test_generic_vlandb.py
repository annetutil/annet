from collections import OrderedDict
from typing import Any

from annet.annlib.types import Op
from annet.rulebook.generic import vlandb


def _diff(
    *,
    added: tuple[tuple[str, OrderedDict[str, Any]], ...] = (),
    removed: tuple[tuple[str, OrderedDict[str, Any]], ...] = (),
    affected: tuple[tuple[str, OrderedDict[str, Any]], ...] = (),
) -> dict[str, list[dict[str, Any]]]:
    return {
        Op.ADDED: [{"row": row, "children": children} for row, children in added],
        Op.REMOVED: [{"row": row, "children": children} for row, children in removed],
        Op.AFFECTED: [{"row": row, "children": children} for row, children in affected],
        Op.MOVED: [],
        Op.UNCHANGED: [],
    }


def test_simple_ranges_collapses_adjacent_pair():
    diff = _diff(
        added=(("vlan 1000", OrderedDict()), ("vlan 1001", OrderedDict())),
    )

    assert list(vlandb.simple_ranges({}, (), diff)) == [(True, "vlan 1000-1001", None)]


def test_simple_no_tiny_ranges_splits_pair_inside_disjoint_list():
    diff = _diff(
        removed=(("vlan 1000", OrderedDict()), ("vlan 1001", OrderedDict()), ("vlan 1003", OrderedDict())),
    )

    assert list(vlandb.simple_no_tiny_ranges({}, (), diff)) == [(False, "no vlan 1000,1001,1003", None)]


def test_simple_preserves_affected_vlan_children():
    children = OrderedDict({"name SERVERS": OrderedDict()})
    diff = _diff(affected=(("vlan 1000", children),))

    assert list(vlandb.simple_ranges({}, (), diff)) == [(True, "vlan 1000", children)]


def test_simple_can_exclude_new_vlan_blocks_from_plain_additions():
    children = OrderedDict({"name SERVERS": OrderedDict()})
    diff = _diff(added=(("vlan 1000", children),))

    assert list(
        vlandb.simple(
            {},
            (),
            diff,
            tiny_ranges=True,
            exclude_added_blocks=True,
        )
    ) == [(True, "vlan 1000", children)]
