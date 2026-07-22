import socket
from collections.abc import Iterator
from typing import Any

from annet.annlib.types import Op
from annet.rulebook import common


def peer(
    rule: dict[str, Any],
    key: tuple[str, ...],
    diff: dict[str, list[dict[str, Any]]],
    root_pre: dict[str, Any],
    **_: Any,
) -> Iterator[tuple[bool, str, Any]]:  # pylint: disable=unused-argument
    """
    The peculiarity of peer commands is that
        peer IP as-number N
    is the main command, and it can only be removed with
        undo peer IP
    which completely deletes all settings of the peer.
    At the same time, the as-number can also be set for a group:
        group SPINES
        peer SPINES as-number 13238
    In this case, we ignore it and allow this setting to be deleted, since it does not define the group itself:
        undo peer SPINES as-number
    """

    assert not diff[Op.AFFECTED], "Peer commands could not contain subcommands"
    removed_as_number = any(_is_as_number_row(action["row"]) for action in diff[Op.REMOVED])
    added_as_number = any(_is_as_number_row(action["row"]) for action in diff[Op.ADDED])
    is_as_number_replaced = removed_as_number and added_as_number
    added_group = any(_is_group_row(action["row"]) for action in diff[Op.ADDED])

    if added_group and _is_ip_addr(key[0]):
        # Assigning an existing H3C peer to a group resets its peer-level settings.
        # Restore settings that are unchanged in the target configuration as well.
        _restore_unchanged_ip_peer_settings(root_pre, key[0])

    if removed_as_number and _is_ip_addr(key[0]):
        # `undo peer IP` removes all peer settings, including unchanged ones and address-family options.
        # Suppress their redundant removals and restore desired settings when replacing the ASN.
        _prepare_ip_peer_reset(root_pre, key[0], restore_unchanged=is_as_number_replaced)
        # This is intentionally marked as direct: h3c.order places it immediately before the new as-number.
        yield (is_as_number_replaced, "undo peer {}".format(*key), None)

    for action in sorted(diff[Op.REMOVED], key=lambda act: not _is_as_number_row(act["row"])):
        tokens = action["row"].split()
        (_, addr_or_group_name, param, *__) = tokens
        if param == "as-number":
            if _is_ip_addr(addr_or_group_name):
                yield (False, "undo peer {}".format(*key), None)
            else:
                # We can’t use common.default because the rule is defined as "peer *" and not "peer * *".
                # Therefore, the default behavior here would be "undo peer PEERGROUP", which is not what we want.
                yield (is_as_number_replaced, "undo peer {} as-number".format(*key), None)
            break

        if param in ["connect-interface", "ebgp-max-hop", "local-as", "substitute-as", "password", "preferred-value"]:
            yield (False, "undo " + " ".join(tokens[:3]), None)
        else:
            yield (False, "undo " + action["row"], None)

    for action in sorted(diff[Op.ADDED], key=lambda act: not _is_as_number_row(act["row"])):
        yield (True, action["row"], None)


def bfd(
    rule: dict[str, Any], key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], **_: Any
) -> Iterator[tuple[bool, str, Any]]:
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


def _prepare_ip_peer_reset(pre: dict[str, Any], peer: str, *, restore_unchanged: bool) -> None:
    """Adjust peer operations after H3C removes the complete peer configuration."""
    for rule_pre in pre.values():
        for item_diff in rule_pre["items"].values():
            if restore_unchanged:
                for action in list(item_diff[Op.UNCHANGED]):
                    children = action["children"]
                    if children:
                        _prepare_ip_peer_reset(children, peer, restore_unchanged=True)
                        if _has_patch_operations(children):
                            _move_action(item_diff, Op.UNCHANGED, Op.AFFECTED, action)
                    elif _is_peer_row(action["row"], peer):
                        _move_action(item_diff, Op.UNCHANGED, Op.ADDED, action)

            for action in list(item_diff[Op.REMOVED]):
                if not action["children"] and _is_peer_row(action["row"], peer):
                    item_diff[Op.REMOVED].remove(action)

            for action in list(item_diff[Op.AFFECTED]):
                children = action["children"]
                if children:
                    _prepare_ip_peer_reset(children, peer, restore_unchanged=restore_unchanged)
                    if not _has_patch_operations(children):
                        _move_action(item_diff, Op.AFFECTED, Op.UNCHANGED, action)


def _restore_unchanged_ip_peer_settings(pre: dict[str, Any], peer: str) -> None:
    """Restore settings cleared when H3C assigns an existing peer to a group."""
    for rule_pre in pre.values():
        for item_diff in rule_pre["items"].values():
            for action in list(item_diff[Op.UNCHANGED]):
                children = action["children"]
                if children:
                    _restore_unchanged_ip_peer_settings(children, peer)
                    if _has_patch_operations(children):
                        _move_action(item_diff, Op.UNCHANGED, Op.AFFECTED, action)
                elif _is_peer_row(action["row"], peer):
                    _move_action(item_diff, Op.UNCHANGED, Op.ADDED, action)

            for action in item_diff[Op.AFFECTED]:
                if action["children"]:
                    _restore_unchanged_ip_peer_settings(action["children"], peer)


def _has_patch_operations(pre: dict[str, Any]) -> bool:
    return any(
        item_diff[op]
        for rule_pre in pre.values()
        for item_diff in rule_pre["items"].values()
        for op in (Op.ADDED, Op.REMOVED, Op.AFFECTED, Op.MOVED)
    )


def _is_peer_row(row: str, peer: str) -> bool:
    tokens = row.split()
    return len(tokens) >= 2 and tokens[:2] == ["peer", peer]


def _is_as_number_row(row: str) -> bool:
    tokens = row.split()
    return len(tokens) >= 3 and tokens[0] == "peer" and tokens[2] == "as-number"


def _is_group_row(row: str) -> bool:
    tokens = row.split()
    return len(tokens) >= 4 and tokens[0] == "peer" and tokens[2] == "group"


def _move_action(item_diff: dict[str, list[dict[str, Any]]], source: str, target: str, action: dict[str, Any]) -> None:
    item_diff[source].remove(action)
    item_diff[target].append(action)


def _bfd_params_used(row: str) -> Iterator[str]:
    prev = None
    for token in row.split():
        if prev and token.isnumeric():
            if prev and token.isnumeric():
                yield prev
        prev = token
