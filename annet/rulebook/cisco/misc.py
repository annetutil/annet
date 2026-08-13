import re
from collections import OrderedDict
from collections.abc import Iterator
from typing import Any

from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.types import Op
from annet.rulebook import common


def ssh_key(
    rule: dict[str, Any], key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], hw: HardwareView, **_: Any
) -> Iterator[tuple[bool, str, Any]]:
    """
    When ssh is enabled a key has to be generated as well.
    There is no way to tell from the config whether the switch has a key.
    """
    if diff[Op.ADDED]:
        added = sorted([x["row"] for x in diff[Op.ADDED]])
        if added == ["ip ssh version 2"]:
            # Give mpdaemon some hints about the extra command needed during provisioning
            comment = rule["comment"]
            rule["comment"] = ["!!suppress_errors!!", "!!timeout=240!!"]
            if hw.Cisco.Catalyst.C2900.C2960:
                yield (False, "crypto key generate rsa modulus 2048", None)
            else:
                yield (False, "crypto key generate rsa general-keys modulus 2048", None)
            rule["comment"] = comment
    yield from common.default(rule, key, diff)


def no_ipv6_nd_suppress_ra(
    rule: dict[str, Any], key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], **_: Any
) -> Iterator[tuple[bool, str, Any]]:
    """
    When configuring ipv6 nd on nexus devices
    no ipv6 nd suppress-ra
    has to be added, otherwise RA will not be enabled.
    Unfortunately this command is not visible in the running-config.
    That is why we mix it into the patch instead of the generator
    """
    if diff[Op.ADDED]:
        yield (False, "no ipv6 nd suppress-ra", None)
    yield from common.default(rule, key, diff)


def no_ntp_distribute(
    rule: dict[str, Any], key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], **_: Any
) -> Iterator[tuple[bool, str, Any]]:
    """
    To remove NTP from CFS, the active NTP sessions have to be cleared first.
    """
    if diff[Op.REMOVED]:
        yield (False, "clear ntp session", None)
    yield from common.default(rule, key, diff)


def banner_any(
    rule: dict[str, Any], key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], **_: Any
) -> Iterator[tuple[bool, str, Any]]:
    if diff[Op.ADDED]:
        # Strip the extra escaping character
        banner = re.sub(r"\^C", "^", diff[Op.ADDED][0]["row"])
        yield (False, banner, None)
    elif diff[Op.REMOVED]:
        yield (False, f"no banner {key[0]}", None)
    else:
        yield from common.default(rule, key, diff)
