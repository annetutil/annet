import socket
from collections.abc import Iterator
from typing import Any

from annet.annlib.types import Op
from annet.rulebook import common


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
