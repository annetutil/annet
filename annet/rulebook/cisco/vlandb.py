from collections.abc import Iterator
from typing import Any

from annet.annlib.lib import cisco_collapse_vlandb as collapse_vlandb
from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.types import Op
from annet.rulebook.generic import vlandb as generic_vlandb


SWTRUNK_CHUNK = 5


# =====
def simple(
    rule: dict[str, Any], key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], hw: HardwareView, **_: Any
) -> Iterator[tuple[bool, str, Any]]:
    yield from generic_vlandb.simple(
        rule,
        key,
        diff,
        tiny_ranges=bool(hw.Cisco.Catalyst),
        exclude_added_blocks=bool(hw.Cisco.Catalyst),
    )


def swtrunk(
    rule: dict[str, Any], key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], hw: HardwareView, **_: Any
) -> Iterator[tuple[bool, str, Any]]:
    # pylint: disable=unused-argument
    for affected in diff[Op.AFFECTED]:
        # The contents of the vlan block have changed
        yield (True, affected["row"], affected["children"])

    (prefix, new, _new_blocks) = generic_vlandb.parse_actions(diff[Op.ADDED])
    (prefix2, old, _old_blocks) = generic_vlandb.parse_actions(diff[Op.REMOVED])
    if not prefix:
        prefix = prefix2

    if not new:
        if diff[Op.ADDED] and not diff[Op.UNCHANGED]:
            # switchport trunk allowed vlan none
            yield (True, "%s none" % prefix, None)
            return
        if diff[Op.REMOVED] and not diff[Op.UNCHANGED]:
            # no switchport trunk allowed vlan
            yield (False, "no %s" % prefix, None)
            return

    removed = old.difference(new)
    added = new.difference(old)
    if removed:
        collapsed = collapse_vlandb(removed, bool(hw.Cisco.Catalyst))
        for chunk in generic_vlandb.iter_chunks(collapsed, SWTRUNK_CHUNK):
            yield (True, "%s%s%s" % (prefix, " remove ", ",".join(chunk)), None)

    if added:
        collapsed = collapse_vlandb(added, bool(hw.Cisco.Catalyst))
        if not old:
            # by default all vlans are allowed
            # switchport trunk allowed vlan none
            yield (True, "%s none" % prefix, None)
        for chunk in generic_vlandb.iter_chunks(collapsed, SWTRUNK_CHUNK):
            yield (True, "%s%s%s" % (prefix, " add ", ",".join(chunk)), None)
