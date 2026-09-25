import socket
from collections import OrderedDict
from collections.abc import Iterable, Iterator
from typing import Any

from annet.annlib.types import Op
from annet.rulebook import common
from annet.rulebook.common import DiffItem


def undo_commit(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any) -> common.LogicResult:
    # Huawei does not allow dropping the bgp configuration and writing it again in a single commit. It says:
    #    Invalid configuration. BGP is under undo.
    # when trying to create a new one after the removal
    if diff[Op.REMOVED]:
        rule["force_commit"] = True
        yield (False, rule["reverse"], None)
    # the commit is required under undo bgp
    rule["force_commit"] = False
    yield from common.default(rule, key, diff)


def peer(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any) -> common.LogicResult:  # pylint: disable=unused-argument  # noqa: E501
    """
    The peculiarity of the peer commands is that
        peer IP as-number N
    is the main command, and it can only be cancelled with
        undo peer IP
    i.e. by removing all the settings of the peer.

    At the same time as-number can also be set for a group:
        group SPINES
        peer SPINES as-number 13238
    in that case it is ignored: this setting may be removed since it does not define the group
        undo peer SPINES as-number
    """

    assert not diff[Op.AFFECTED], "Peer commands could not contain subcommands"
    for action in sorted(diff[Op.REMOVED], key=lambda act: "as-number" not in act["row"].split()):
        tokens = action["row"].split()
        (_, addr_or_group_name, param, *__) = tokens
        if param == "as-number":
            if _is_ip_addr(addr_or_group_name):
                yield (False, "undo peer {}".format(*key), None)
            else:
                # we cannot use common.default because the rule is declared as peer * and not peer * *
                # so the default behaviour here would be "undo peer PEERGROUP", which is not what we want
                yield (False, "undo peer {} as-number".format(*key), None)
            break

        if param in ["connect-interface", "ebgp-max-hop", "local-as", "substitute-as", "password", "preferred-value"]:
            yield (False, "undo " + " ".join(tokens[:3]), None)
        else:
            yield (False, "undo " + action["row"], None)

    for action in sorted(diff[Op.ADDED], key=lambda act: "as-number" not in act["row"]):
        yield (True, action["row"], None)


def bfd(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any) -> common.LogicResult:
    """
    [*vla-1x1-bgp]undo peer SPINE1 bfd min-tx-interval 500 min-rx-interval 500 detect-multiplier 4
    │Error: Unrecognized command found at '^' position.

    [*vla-1x1-bgp]undo peer SPINE1 bfd min-rx-interval
    [~vla-1x1-bgp]undo peer SPINE1 bfd min-tx-interval
    [*vla-1x1-bgp]undo peer SPINE1 bfd detect-multiplier
    """
    if diff[Op.REMOVED]:
        assert len(diff[Op.REMOVED]) <= 1 and len(diff[Op.ADDED]) <= 1
        new_params = set()
        if diff[Op.ADDED]:
            new_params = set(_bfd_params_used(diff[Op.ADDED][0]["row"]))
        for token in _bfd_params_used(diff[Op.REMOVED][0]["row"]):
            if token not in new_params:
                yield (False, rule["reverse"].format(*key) + " " + token, None)
        diff[Op.REMOVED] = []
    if diff[Op.ADDED]:
        yield from common.default(rule, key, diff, **_)


def reapply_after_as_number_change(
    old: OrderedDict[str, Any],
    new: OrderedDict[str, Any],
    diff_pre: OrderedDict[str, Any],
    _pops: tuple[str, ...] = (Op.AFFECTED,),
) -> list[DiffItem]:
    """
    On Huawei, removing or changing the as-number of an existing IP peer
    triggers `undo peer <ip>`, which wipes every `peer <ip> ...` command in
    the same scope. The default diff doesn't reflect this implicit wipe, so
    we rewrite the bgp subtree here:

    1. AS-number CHANGE on an IP peer: the peer's other rows are identical in
       old and new, so the default diff marks them UNCHANGED and they are
       never re-sent — leaving the device with a half-configured peer. We
       flip those AFFECTED rows to ADDED so the patcher re-emits them after
       `undo peer <ip>`.

    2. AS-number CHANGE / full IP-peer REMOVAL: any REMOVED rows for the same
       IP become redundant and would error against a nonexistent peer
       ("Error: The peer session does not exist"). We drop them.

    The `peer <ip> as-number ...` row can live at the bgp top level or inside
    an address-family / vpn-instance block, so the wiped/recreated sets are
    computed per block (see `_rewrite_block`). A bgp top-level `undo peer
    <ip>` wipes the peer in the global family blocks too, so the set is
    inherited downward — but it stops at a `vpn-instance` boundary, since a
    vpn-instance peer is a separate namespace and its `undo peer <ip>` is
    issued (and only wipes) within that block.

    Scope: IP peers only. Peer-group renames go through a different
    Huawei command (`undo peer <group> as-number`, non-destructive) and
    don't need re-emit. Peer-group removal isn't handled here either; the
    pre-PR per-option-undo shape is correct on the device (just noisier).

    Group members: `peer <ip> group <G>` makes the device add the member's
    own `peer <ip> as-number <group AS>` row to the running config
    automatically. It is the generator's responsibility to yield that row
    for every group member; otherwise annet sees it as REMOVED and emits
    `undo peer <ip>`, wiping the peer, on every run. The same applies to
    the rows the device adds under `ipv4-family unicast` (`peer <ip> enable`
    and `peer <ip> group <G>` without `undo default ipv4-unicast`).
    """
    items = common.default_diff(old, new, diff_pre, _pops)

    result = []
    for item in items:
        bgp_old = old.get(item.row, {})
        bgp_new = new.get(item.row, {})
        children = _rewrite_block(item.children, bgp_old, bgp_new, set(), set())
        result.append(item._replace(children=children))
    return result


def _wiped_peer_ips(old: OrderedDict[str, Any], new: OrderedDict[str, Any]) -> set[str]:
    """IPs whose `peer <ip> as-number ...` row at this level is in `old` but
    not in `new` — i.e. peers for which peer() will emit `undo peer <ip>`
    (covers both full removal and as-number value change)."""
    wiped_peer_ips = set()
    for row in old:
        if row in new or not _is_peer_as_number_row(row):
            continue
        key = row.split()[1]
        if _is_ip_addr(key):
            wiped_peer_ips.add(key)
    return wiped_peer_ips


def _peer_ips_with_as_number(rows: Iterable[str]) -> set[str]:
    """IPs that appear in a `peer <ip> as-number ...` row at this level."""
    peer_ips = set()
    for row in rows:
        if not _is_peer_as_number_row(row):
            continue
        key = row.split()[1]
        if _is_ip_addr(key):
            peer_ips.add(key)
    return peer_ips


def _peer_key(row: str) -> str | None:
    """Peer name/IP of a `peer <x> ...` or `undo peer <x> ...` row. The
    latter matters for `undo peer <ip> enable` in a family block: without
    `undo default ipv4-unicast` a recreated peer comes back enabled, so the
    row has to be re-sent after the wipe like any other peer row."""
    tokens = row.split()
    if tokens and tokens[0] == "undo":
        tokens = tokens[1:]
    if len(tokens) >= 2 and tokens[0] == "peer":
        return tokens[1]
    return None


def _is_peer_as_number_row(row: str) -> bool:
    tokens = row.split()
    return len(tokens) >= 3 and tokens[0] == "peer" and tokens[2] == "as-number"


def _is_vpn_instance_block(row: str) -> bool:
    return "vpn-instance" in row.split()


def _rewrite_block(
    items: list[DiffItem],
    old_level: OrderedDict[str, Any],
    new_level: OrderedDict[str, Any],
    inherited_wiped: set[str],
    inherited_recreated: set[str],
) -> list[DiffItem]:
    """Rewrite one block of the bgp subtree (the bgp body itself, or a family
    / vpn-instance block). `old_level`/`new_level` are this block's old/new
    config dicts, used to find peers wiped at this scope.

    `wiped` is the set of IPs whose `peer <ip> as-number ...` row disappears
    at this scope or any enclosing one; `recreated` is the subset that still
    has an as-number row in `new` (renumbered, not removed). For each
    `peer <ip> ...` DiffItem whose IP is wiped:
      - REMOVED rows are dropped (redundant after the upstream `undo peer
        <ip>`), except a REMOVED `peer <ip> as-number Y` row, which is kept
        as the trigger that makes huawei.bgp.peer emit `undo peer <ip>`;
      - AFFECTED rows are flipped to ADDED for a recreated IP, so the
        re-declared peer's other rows are re-applied after the wipe.

    A `vpn-instance` block is a separate peer namespace, so the inherited
    sets are not carried across that boundary — only the block's own peers
    apply inside it."""
    local_wiped = _wiped_peer_ips(old_level, new_level)
    wiped = inherited_wiped | local_wiped
    recreated = inherited_recreated | (local_wiped & _peer_ips_with_as_number(new_level))

    result = []
    for item in items:
        key = _peer_key(item.row)
        is_wiped_peer = key in wiped
        if is_wiped_peer and item.op == Op.REMOVED and not _is_peer_as_number_row(item.row):
            continue
        if _is_vpn_instance_block(item.row):
            child_wiped, child_recreated = set(), set()
        else:
            child_wiped, child_recreated = wiped, recreated
        children = _rewrite_block(
            item.children,
            old_level.get(item.row, {}),
            new_level.get(item.row, {}),
            child_wiped,
            child_recreated,
        )
        if is_wiped_peer and item.op == Op.AFFECTED and key in recreated:
            result.append(item._replace(op=Op.ADDED, children=children))
        else:
            result.append(item._replace(children=children))
    return result


def _is_ip_addr(addr_or_string: str) -> bool:
    ret = None
    for af in (socket.AF_INET6, socket.AF_INET):
        try:
            ret = socket.inet_pton(af, addr_or_string)
        except OSError:
            pass
        else:
            break
    return bool(ret)


def _bfd_params_used(row: str) -> Iterator[str]:
    prev = None
    for token in row.split():
        if prev and token.isnumeric():
            if prev and token.isnumeric():
                yield prev
        prev = token
