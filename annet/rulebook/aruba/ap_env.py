# pylint: disable=unused-argument

from collections.abc import Iterator
from typing import Any

from annet.annlib.command import Command, CommandList
from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.rulebook.common import DiffDict
from annet.annlib.types import Op


def apply(hw: HardwareView, do_commit: bool, do_finalize: bool, **_: Any) -> tuple[CommandList, CommandList]:
    before, after = CommandList(), CommandList()
    if do_commit:
        after.add_cmd(Command("write memory"))
    return (before, after)


def patch_flag(
    rule: dict[str, Any], key: tuple[str, ...], diff: DiffDict, **_: Any
) -> Iterator[tuple[bool, str, None]]:
    direct: bool | None = None
    cmd = ""
    if diff[Op.ADDED]:
        row, _ = diff[Op.ADDED][0]["row"].split(":")
        cmd = row.replace("_", "-")
        direct = True
    elif diff[Op.REMOVED]:
        row, _ = diff[Op.REMOVED][0]["row"].split(":")
        cmd = "no " + row.replace("_", "-")
        direct = False
    if cmd:
        assert direct is not None
        yield direct, cmd, None


def hostname(rule: dict[str, Any], key: tuple[str, ...], diff: DiffDict, **_: Any) -> Iterator[tuple[bool, str, None]]:
    if diff[Op.ADDED]:
        yield True, "hostname %s" % key, None


def mgmt(
    rule: dict[str, Any], key: tuple[str, ...], diff: DiffDict, rule_pre: dict[str, Any], **_: Any
) -> Iterator[tuple[bool, str, None]]:
    if not diff[Op.ADDED] and not diff[Op.REMOVED]:
        return
    pre_items = rule_pre["items"]
    unchanged = {k[0]: v[Op.UNCHANGED][0]["row"].split(":")[1] for k, v in pre_items.items() if v[Op.UNCHANGED]}
    added = {k[0]: v[Op.ADDED][0]["row"].split(":")[1] for k, v in pre_items.items() if v[Op.ADDED]}
    params: dict[str, str | None] = {
        "ipaddr": None,
        "netmask": None,
        "gatewayip": None,
        "dnsip": None,
        "domainname": None,
    }
    params.update({k: v for k, v in unchanged.items() if k in params})
    params.update({k: v for k, v in added.items() if k in params})
    empty = {k: v for k, v in params.items() if v is None}
    if empty:
        raise RuntimeError("Failed to determine params %s" % ",".join(empty.keys()))
    yield (
        True,
        f"ip-address {params['ipaddr']} {params['netmask']} {params['gatewayip']} {params['dnsip']} "
        f"{params['domainname']}",
        None,
    )


def swarm_mode(
    rule: dict[str, Any], key: tuple[str, ...], diff: DiffDict, **_: Any
) -> Iterator[tuple[bool, str, None]]:
    if diff[Op.ADDED]:
        row = diff[Op.ADDED][0]["row"]
        mode = row.split("_")[0]
        yield True, "swarm-mode %s" % mode, None
    elif diff[Op.REMOVED]:
        yield True, "swarm-mode cluster", None


def iap_zone(rule: dict[str, Any], key: tuple[str, ...], diff: DiffDict, **_: Any) -> Iterator[tuple[bool, str, None]]:
    if diff[Op.ADDED]:
        yield True, "zone %s" % key, None


def dot11_radio(
    rule: dict[str, Any], key: tuple[str, ...], diff: DiffDict, **_: Any
) -> Iterator[tuple[bool, str, None]]:
    direct: bool | None = None
    cmd = ""
    if diff[Op.ADDED]:
        direct, cmd = True, diff[Op.ADDED][0]["row"]
    elif diff[Op.REMOVED]:
        direct, cmd = False, "no " + diff[Op.REMOVED][0]["row"]
    if cmd:
        cmd = cmd.replace("_", "-")
        cmd = cmd.replace(":", "-")
        assert direct is not None
        yield direct, cmd, None


def installation_type(
    rule: dict[str, Any], key: tuple[str, ...], diff: DiffDict, **_: Any
) -> Iterator[tuple[bool, str, None]]:
    if diff[Op.ADDED]:
        row = diff[Op.ADDED][0]["row"]
        _, installation_place = row.split(":")
        yield True, "ap-installation %s" % installation_place, None
    elif diff[Op.REMOVED]:
        yield True, "ap-installation default", None


def wifi_arm(
    rule: dict[str, Any], key: tuple[str, ...], diff: DiffDict, root_pre: dict[str, Any], **_: Any
) -> Iterator[tuple[bool, str, None]]:
    if key[0].startswith("wifi0"):
        prefix, cmd = "wifi0", "a-channel"
    elif key[0].startswith("wifi1"):
        prefix, cmd = "wifi1", "g-channel"
    else:
        raise ValueError("Unknown wifi channel key %r" % key)
    pre_items = list(root_pre.values())[0]["items"]
    unchanged = {k[0]: v[Op.UNCHANGED][0]["row"] for k, v in pre_items.items() if v[Op.UNCHANGED]}
    added = {k[0]: v[Op.ADDED][0]["row"] for k, v in pre_items.items() if v[Op.ADDED]}
    key_arm_channel = prefix + "_arm_channel"
    key_arm_power = prefix + "_arm_power_10x"
    arm_channel, arm_power = "0", "0"
    for params in [unchanged, added]:
        if key_arm_channel in params:
            _, arm_channel = params[key_arm_channel].split(":")
        if key_arm_power in params:
            _, arm_power = params[key_arm_power].split(":")
    yield True, f"{cmd} {arm_channel} {arm_power}", None


def ant_gain(
    rule: dict[str, Any], key: tuple[str, ...], diff: DiffDict, root_pre: dict[str, Any], **_: Any
) -> Iterator[tuple[bool, str, None]]:
    row, value = "", ""
    direct: bool | None = None
    if diff[Op.ADDED]:
        row = diff[Op.ADDED][0]["row"]
        _, value = row.split(":")
        direct = True
    elif diff[Op.REMOVED]:
        row = diff[Op.REMOVED][0]["row"]
        value = "0"
        direct = False
    if row:
        if row.startswith("a_"):
            cmd = "a-external-antenna"
        elif row.startswith("g_"):
            cmd = "g-external-antenna"
        else:
            raise ValueError("Unknown row '%s'" % row)
        assert direct is not None
        yield direct, f"{cmd} {value}", None


def ant_pol(
    rule: dict[str, Any], key: tuple[str, ...], diff: DiffDict, root_pre: dict[str, Any], **_: Any
) -> Iterator[tuple[bool, str, None]]:
    row, value = "", ""
    direct: bool | None = None
    if diff[Op.ADDED]:
        row, value = diff[Op.ADDED][0]["row"].split(":")
        direct = True
    elif diff[Op.REMOVED]:
        row, _ = diff[Op.REMOVED][0]["row"].split(":")
        value = "0"
        direct = False
    if row:
        cmd = row.replace("_", "-")
        assert direct is not None
        yield direct, f"{cmd} {value}", None
