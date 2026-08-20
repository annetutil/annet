import copy
import re
from collections import namedtuple
from collections.abc import Iterator
from typing import Any

from contextlog import get_logger

from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.types import Op
from annet.rulebook import common


class VRPVersion(namedtuple("VRPVersionBase", ["V", "R", "C", "SPC"])):
    ANY = object()
    ATTR_NAMES = ["V", "R", "C", "SPC"]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return False

        for attr_name in self.ATTR_NAMES:
            self_attr = getattr(self, attr_name)
            if self_attr is self.ANY:
                continue
            other_attr = getattr(other, attr_name)
            if other_attr is self.ANY:
                continue

            if self_attr != other_attr:
                return False

        return True

    def __ne__(self, other: object) -> bool:
        return not self == other


def parse_version(version: str) -> VRPVersion:
    # CP - Cold Patch
    # HP - Hot Patch
    if not version:
        # FIXME: maybe, if RT has no data, we should ask the device itself?
        version = "VRP V200R002C50SPC800"
        get_logger().warning("SW version not set, falling back to %r", version)
    res = re.match(r"(?:VRP )?V(?P<v>\d+)R(?P<r>\d+)C(?P<c>\d+)(SPC(?P<spc>\d+))?(?P<opt>T)?", version)
    assert res is not None, f"can't parse version '{version}'"
    m = res.groupdict()  # pylint: disable=invalid-name
    return VRPVersion(int(m["v"]), int(m["r"]), int(m["c"] or 0), int(m["spc"] or 0))


# =====
def rp_node(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any) -> common.LogicResult:
    # route-policy NAME ACTION node NUM
    (rp_name, node_id) = key
    if diff[Op.REMOVED]:
        if diff[Op.ADDED]:
            sub_diff: dict[str, list[dict[str, Any]]] = {
                Op.AFFECTED: [],
                Op.ADDED: [],
                Op.REMOVED: [],
                Op.MOVED: [],
                Op.UNCHANGED: [],
            }
            sub_diff[Op.AFFECTED] = diff[Op.REMOVED]
            yield from common.default(rule, key, sub_diff)
        else:
            yield (False, "undo route-policy %s node %s" % (rp_name, node_id), None)

    if diff[Op.AFFECTED] or diff[Op.ADDED]:
        yield from common.default(rule, key, diff)


def undo_redo(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any) -> common.LogicResult:
    yield from common.undo_redo(rule, key, diff, **_)


def prefix_list(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **kwargs: Any) -> common.LogicResult:
    # to determine whether the prefix list is replaced entirely,
    # the huawei.rul rulebook declares the key as (family, name)
    # from the command point of view, however, every index is a separate command,
    # so we group them by index here and pass them on to common
    diff_by_index: dict[str, common.DiffDict] = {}
    for op, rows in diff.items():
        for row in rows:
            # expected format of a prefix-list command
            # ip ip-prefix PRFX_CT_LU_ALLOWED_ROUTES index 15 ..
            # ip ipv6-prefix PFXS_SPECIALv6 index 20 ..
            _ip, _family, _name, _index, index, *_ = row["row"].split()
            if index not in diff_by_index:
                sub_diff: dict[str, list[dict[str, Any]]] = {op: [] for op in diff.keys()}
                diff_by_index[index] = sub_diff
            diff_by_index[index][op].append(row)

    family, name = key
    if family not in {"ip", "ipv6"}:
        raise NotImplementedError("Unknown family '%s'" % family)
    if diff[Op.ADDED] or diff[Op.REMOVED] or diff[Op.MOVED]:
        # since the rule key originally has no index in it,
        # it has to be added there, otherwise the undo rule would come without one
        indexed_rule = copy.deepcopy(rule)
        indexed_rule["reverse"] = "undo ip {}-prefix {} index {}"

        # stub_index is referenced in the huawei.order rulebook to make sure
        # the stub is added first and removed last
        stub, stub_index = "", 99999999

        # if we only add new commands to the prefix list (e.g. create it),
        # or remove/move them while some parts stay unchanged,
        # huawei will not consider the list removed and the stub rule is not needed
        if (diff[Op.REMOVED] or diff[Op.MOVED]) and not diff[Op.UNCHANGED]:
            stub = "deny 0.0.0.0 32" if family == "ip" else "deny :: 128"
        if stub:
            yield (True, f"ip {family}-prefix {name} index {stub_index} {stub}", None)
        for index, sub_diff in diff_by_index.items():
            yield from common.undo_redo(indexed_rule, (family, name, index), sub_diff, **kwargs)
        if stub:
            yield (False, f"undo ip {family}-prefix {name} index {stub_index}", None)


def static(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any) -> common.LogicResult:
    """
    To roll a static route back almost every argument has to be passed in,
    except for the various track ...
    The number of arguments may vary though - an optional VRF, an optional interface.
    That is why we do not parse the command itself and only drop the unneeded arguments.
    """
    if diff[Op.REMOVED]:
        param = key[0]
        idx = param.find(" track")
        if idx > 0:
            key = (param[0:idx],)
        idx = param.find(" description")
        if idx > 0:
            key = (param[0:idx],)
        idx = param.find(" preference")
        if idx > 0:
            key = (param[0:idx],)
    yield from common.default(rule, key, diff)


def undo_trust(
    rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, hw: HardwareView, **_: Any
) -> common.LogicResult:
    """on CE switches the command is undo trust; on S it is undo trust *"""
    if diff[Op.REMOVED]:
        if hw.Huawei.Quidway and not hw.Huawei.Quidway.S6700:
            yield False, "undo trust %s" % key, None
        else:
            yield False, "undo trust", None
    else:
        yield from common.default(rule, key, diff)


def port_queue(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any) -> common.LogicResult:
    """
    Rolling back the port-queue configuration on an interface requires only part of the parameters.
    Example of disabling/enabling:
    interface 100GE0/1/33
        undo port-queue af3 wfq outbound
        port-queue af3 wfq weight 30 port-wred WRED outbound

    Essentially all the parameters between 'wfq' and 'outbound' have to be removed
    NOC-19414
    """
    if diff[Op.REMOVED]:
        param = key[0]
        idx = param.find("weight")
        if idx > 0:
            key = (param[0:idx] + "outbound",)
    yield from common.default(rule, key, diff)


def netstream_undo(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any) -> common.LogicResult:
    if diff[Op.REMOVED]:
        # The only part we need is the last keyword: inbound or outbound
        # Unfortunately, key is a tuple so we cast it to a list and back
        key_parts = list(key)
        key_parts[1] = key_parts[1].split(" ")[-1]
        key = tuple(key_parts)
    yield from common.default(rule, key, diff)


def undo_dhcp_server_dns_list(
    rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any
) -> common.LogicResult:
    if diff[Op.REMOVED]:
        for dns_server in key[0].split():
            yield False, rule["reverse"].format(dns_server), None
    else:
        yield from common.default(rule, key, diff)


def old_snmp_iface_trap_undo(
    rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, hw: HardwareView, **_: Any
) -> common.LogicResult:
    # tricky logic for old huawei devices
    # here an incomplete row has to be generated instead of the full command with undo
    if diff[Op.REMOVED]:
        if hw.Huawei.Quidway:
            yield False, "undo mac-address trap notification", None
        else:
            yield False, "undo mac-address trap notification learn", None
    else:
        yield from common.default(rule, key, diff)


def stelnet(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any) -> common.LogicResult:
    # do not replace the rows stelnet ipv4 server enable and stelnet ipv6 server enable with stelnet server enable
    # so that SSH is not disturbed
    if diff[Op.REMOVED] and diff[Op.ADDED]:
        removed = {x["row"] for x in diff[Op.REMOVED]}
        added = {x["row"] for x in diff[Op.ADDED]}
        if removed == {"stelnet ipv4 server enable", "stelnet ipv6 server enable"} and added == {
            "stelnet server enable"
        }:
            return
    yield from common.default(rule, key, diff)


def snmpagent_sysinfo_version(
    rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, hw: HardwareView, **_: Any
) -> common.LogicResult:
    if hw.Huawei.CE and (diff[Op.ADDED] or diff[Op.REMOVED]):
        assert len(diff[Op.AFFECTED]) == 0, "WTF? Affected not empty: %r" % (diff[Op.AFFECTED])
        versions = set(["v1", "v2c", "v3"])

        result = set()
        for op in [Op.REMOVED, Op.ADDED]:
            for action in diff[op]:
                args = action["row"].split()[3:]
                assert len(args) > 0, "Empty op %r: %r" % (op, action["row"])

                if args[-1] == "disable":
                    args = args[:-1]
                    disable = True
                else:
                    disable = False
                if "all" in args:
                    args = versions
                else:
                    assert len(set(args).difference(versions)) == 0, "Incorrect args: %r" % (args)

                if (op == Op.REMOVED and disable) or (op == Op.ADDED and not disable):
                    result.update(args)
                else:
                    result.difference_update(args)

        if result == versions:
            yield (True, "snmp-agent sys-info version all", None)
        else:
            yield (False, "snmp-agent sys-info version all disable", None)
            yield (True, "snmp-agent sys-info version %s" % (" ".join(result)), None)
    else:
        yield from common.default(rule, key, diff)


def vty_acl_undo(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any) -> common.LogicResult:
    if diff[Op.REMOVED]:
        chunks = key[0].split()
        result_chunks = ["undo acl"]
        if len(chunks) == 3 and chunks[0] == "ipv6":
            result_chunks.append("ipv6")
        result_chunks.append(chunks[-1])
        yield False, " ".join(result_chunks), None
    else:
        yield from common.default(rule, key, diff)


def port_split(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any) -> common.LogicResult:
    # pylint: disable=unused-argument
    def _port_split(old: list[str], new: list[str], old_row: str, new_row: str) -> Iterator[tuple[bool, str, None]]:
        removed = set(old).difference(new)
        added = set(new).difference(old)
        if old and new:
            for ifname in removed:
                yield (False, "undo port split dimension interface " + ifname, None)
            for ifname in added:
                yield (True, "port split dimension interface " + ifname, None)
        elif old and not new:
            yield (False, "undo " + old_row, None)
        elif new and not old:
            yield (True, new_row, None)

    def _row_slot(row: str) -> int:
        res = ""
        for ch in row:
            if ch == "/":
                break
            res = res + ch if ch.isnumeric() else ""
        return int(res) if res else 0

    old_by_slot = {_row_slot(x["row"]): x["row"] for x in diff[Op.REMOVED]}
    new_by_slot = {_row_slot(x["row"]): x["row"] for x in diff[Op.ADDED]}
    for slot in set(old_by_slot.keys()).union(new_by_slot.keys()):
        old_row = old_by_slot[slot] if slot in old_by_slot else ""
        new_row = new_by_slot[slot] if slot in new_by_slot else ""
        old = _expand_portsplit(old_row)
        new = _expand_portsplit(new_row)
        yield from _port_split(old, new, old_row, new_row)
    if old_by_slot or new_by_slot:
        yield (True, "port split refresh", None)


def _expand_portsplit(row: str) -> list[str]:
    expanded = []
    row_parts = row.split()
    for index, part in enumerate(row_parts):
        if part == "to":
            iface_base = "/".join(row_parts[index - 1].split("/")[:-1])
            left = int(row_parts[index - 1].split("/")[-1])
            right = int(row_parts[index + 1].split("/")[-1])
            for i in range(left + 1, right):
                expanded.append(iface_base + "/" + str(i))
        else:
            expanded.append(part)
    return expanded


def classifier(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any) -> common.LogicResult:
    # if the type changes, all the if-match entries have to be removed first
    # and only after that the classifier is re-created
    if diff[Op.ADDED] and diff[Op.REMOVED]:
        yield (True, diff[Op.REMOVED][0]["row"], diff[Op.REMOVED][0]["children"])
    yield from common.default(rule, key, diff)


def undo_children(rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any) -> common.LogicResult:
    def removed_count(subdiff: dict[str, Any]) -> int:
        ret = 0
        for child in subdiff["children"].values():
            for child_diff in child["items"].values():
                ret += len(child_diff[Op.REMOVED])
        return ret

    def common_default(op: str, subdiff: dict[str, Any]) -> common.LogicResult:
        newdiff: dict[str, list[dict[str, Any]]] = {
            Op.ADDED: [],
            Op.REMOVED: [],
            Op.MOVED: [],
            Op.AFFECTED: [],
            Op.UNCHANGED: [],
        }
        newdiff[op] = [subdiff]
        yield from common.default(rule, key, newdiff)

    # We have to emit undo ourselves since we pretend to be a single block
    for subdiff in diff[Op.REMOVED]:
        # All the group-members have to be removed first
        if diff[Op.REMOVED][0]["children"]:
            yield (True, diff[Op.REMOVED][0]["row"], diff[Op.REMOVED][0]["children"])
        yield False, "undo " + subdiff["row"], None
    # Handle affected first, since it may contain undo statements inside
    for subdiff in sorted(diff[Op.AFFECTED], key=removed_count, reverse=True):
        yield from common_default(Op.AFFECTED, subdiff)
    for subdiff in diff[Op.ADDED]:
        yield from common_default(Op.ADDED, subdiff)


def clear_instead_undo(
    rule: dict[str, Any], key: tuple[str, ...], diff: common.DiffDict, **_: Any
) -> common.LogicResult:
    # A number of configuration rows produce a permanent diff, because in the config a row is either explicitly enabled
    # or explicitly disabled. If it is not described in the generator, i.e. we rely on the default, then using clear
    # instead of undo returns the config to its default state.
    # NOC-20102 @gslv 11-02-2022
    if diff[Op.REMOVED]:
        if diff[Op.REMOVED][0]["row"].endswith(" disable"):
            cmd = diff[Op.REMOVED][0]["row"].replace(" disable", "")
        yield (True, "clear " + cmd, False)
    else:
        yield from common.default(rule, key, diff)
