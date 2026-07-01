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

# Вырезает все команды не разрешенные
# на членах агрегата. В running-config
# листинге они наследуются от самого port-channel


def _filter_channel_members(tree: OrderedDict[str, Any]) -> None:
    if any(is_in_channel(x) for x in tree):
        for cmd in list(tree.keys()):
            if not _is_allowed_on_channel(cmd):
                del tree[cmd]


def is_in_channel(cmd_line: str) -> bool:
    """
    Признак того, что это lagg member
    """
    return cmd_line.startswith("channel-group")


# Возможно тут есть еще какие-то команды
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
    Удаляем mtu без указания значения
    """
    if diff[Op.REMOVED]:
        yield (False, "no mtu", None)
    elif diff[Op.ADDED]:
        yield from common.default(rule, key, diff, **kwargs)


def description(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **kwargs: Any) -> common.LogicResult:
    """
    Удаляем description без указания значения
    """
    if diff[Op.REMOVED]:
        yield (False, "no description", None)
    elif diff[Op.ADDED]:
        yield from common.default(rule, key, diff, **kwargs)


def sflow(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **kwargs: Any) -> common.LogicResult:
    """
    Команда sflow sampling-rate * direction ingress max-header-size *
    сносится без указания sampling-rate и max-header-size
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
    Обрабатываем блок lldp-agent
    """
    result = common.default(rule, key, diff, **kwargs)
    for op, cmd, ch in result:
        # Не удаляем все что начинается с set, т.к. set перезаписывает предыдущий конфиг
        if diff[Op.REMOVED] and "set lldp" in cmd:
            pass
        # В случае lldp tlv ... select удаляем все что до select
        elif diff[Op.REMOVED] and cmd.endswith("select"):
            yield (op, " ".join(cmd.split()[:-1]), ch)
        else:
            yield (op, cmd, ch)
