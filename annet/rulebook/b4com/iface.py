from collections import OrderedDict
from typing import Any

from annet.annlib.rulebook.common import DiffItem
from annet.annlib.types import Op
from annet.rulebook import common


def diff(
    old: OrderedDict[str, Any],
    new: OrderedDict[str, Any],
    diff_pre: OrderedDict[str, Any],
    _pops: tuple[str, ...] = (Op.AFFECTED,),
) -> list[DiffItem]:
    for iface_row in old:
        _filter_channel_members(old[iface_row])
    for iface_row in new:
        _filter_channel_members(new[iface_row])

    ret = common.default_diff(old, new, diff_pre, _pops)
    vpn_changed = False
    for op, cmd, _, _ in ret:
        if op in {Op.ADDED, Op.REMOVED}:
            vpn_changed |= is_vpn_cmd(cmd)
    if vpn_changed:
        for cmd in list(old.keys()):
            if is_ip_cmd(cmd) and not is_vpn_cmd(cmd):
                del old[cmd]
        ret = common.default_diff(old, new, diff_pre, _pops)
    return ret


# ===

# Strips all the commands that are not allowed
# on the members of an aggregate. In the running-config
# listing they are inherited from the port-channel itself


def _filter_channel_members(tree: OrderedDict[str, Any]) -> None:
    if any(is_in_channel(x) for x in tree):
        for cmd in list(tree.keys()):
            if not _is_allowed_on_channel(cmd):
                del tree[cmd]


def is_in_channel(cmd_line: str) -> bool:
    """
    Whether this is a lagg member
    """
    return cmd_line.startswith("channel-group")


# There may be some more commands here
def _is_allowed_on_channel(cmd_line: str) -> bool:
    return cmd_line.startswith(
        (
            "channel-group",
            "cdp",
            "description",
            "inherit",
            "ip port",
            "ipv6 port",
            "mac port",
            "lacp",
            "switchport host",
            "shutdown",
            "rate-limit cpu",
            "snmp trap link-status",
        )
    )


def is_vpn_cmd(cmd: str) -> bool:
    return cmd.startswith("vrf member")


def is_ip_cmd(cmd: str) -> bool:
    return cmd.startswith(("ip ", "ipv6 "))


def mtu(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **kwargs: Any) -> common.LogicResult:
    """
    Remove mtu without specifying the value
    """
    if diff[Op.REMOVED]:
        yield (False, "no mtu", None)
    elif diff[Op.ADDED]:
        yield from common.default(rule, key, diff, **kwargs)


def description(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **kwargs: Any) -> common.LogicResult:
    """
    Remove description without specifying the value
    """
    if diff[Op.REMOVED]:
        yield (False, "no description", None)
    elif diff[Op.ADDED]:
        yield from common.default(rule, key, diff, **kwargs)


def sflow(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **kwargs: Any) -> common.LogicResult:
    """
    The command sflow sampling-rate * direction ingress max-header-size *
    is removed without specifying sampling-rate and max-header-size
    """
    if diff[Op.REMOVED]:
        if "ingress" in diff[Op.REMOVED][0]["row"]:
            yield (False, "no sflow sampling-rate direction ingress", None)
        elif "egress" in diff[Op.REMOVED][0]["row"]:
            yield (False, "no sflow sampling-rate direction egress", None)
        elif "poll-interval" in diff[Op.REMOVED][0]["row"]:
            yield (False, "no sflow poll-interval", None)
    else:
        yield from common.default(rule, key, diff, **kwargs)


def lldp(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **kwargs: Any) -> common.LogicResult:
    """
    Handle the lldp-agent block
    """
    result = common.default(rule, key, diff, **kwargs)
    for op, cmd, ch in result:
        # Do not remove anything that starts with set, since set overwrites the previous config
        if diff[Op.REMOVED] and "set lldp" in cmd:
            pass
        # In case of lldp tlv ... select remove everything up to select
        elif diff[Op.REMOVED] and cmd.endswith("select"):
            yield (op, " ".join(cmd.split()[:-1]), ch)
        else:
            yield (op, cmd, ch)
