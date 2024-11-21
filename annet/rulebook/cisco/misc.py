import re
from collections import OrderedDict
from typing import Any

from annet.annlib.types import Op

from annet.rulebook import common


def ssh_key(rule, key, diff, hw, **_):
    """
    При включении ssh надо еще сгенерировать ключ. По конфигу никак не понять есть ли ключ на свитче или нет.
    """
    if diff[Op.ADDED]:
        added = sorted([x["row"] for x in diff[Op.ADDED]])
        if added == ["ip ssh version 2"]:
            # Отсыпаем mpdaemon-у подсказок для дополнительной команды при наливке
            comment = rule["comment"]
            rule["comment"] = ["!!suppress_errors!!", "!!timeout=240!!"]
            if hw.Cisco.C2960:
                yield (False, "crypto key generate rsa modulus 2048", None)
            else:
                yield (False, "crypto key generate rsa general-keys modulus 2048", None)
            rule["comment"] = comment
    yield from common.default(rule, key, diff)


def no_ipv6_nd_suppress_ra(rule, key, diff, **_):
    """
    При конфигурации ipv6 nd на нексусах нужно добавлять
    no ipv6 nd suppress-ra
    иначе RA не будет включен.
    К сожалению данной команды не видно в running-config.
    Поэтому подмешиваем ее в патч вместо генератора
    """
    if diff[Op.ADDED]:
        yield (False, "no ipv6 nd suppress-ra", None)
    yield from common.default(rule, key, diff)


def no_ntp_distribute(rule, key, diff, **_):
    """
    Для того, чтобы удалить NTP из CFS, сначала нужно сбросить активные
    NTP сессии.
    """
    if diff[Op.REMOVED]:
        yield (False, "clear ntp session", None)
    yield from common.default(rule, key, diff)


def banner_login(rule, key, diff, **_):
    if diff[Op.REMOVED]:
        yield (False, "no banner login", None)
    elif diff[Op.ADDED]:
        # Убираем дополнительный экранирующий сиимвол
        key = re.sub(r"\^C", "^", key[0])
        yield (False, f"banner login {key}", None)
    else:
        yield from common.default(rule, key, diff)


def bgp_diff(old, new, diff_pre, _pops=(Op.AFFECTED,)):
    """
    Some oder versions of Cisco IOS doesn't create subsection for address family block.

    it looks like:

    router bgp 65111
     bgp router-id 1.1.1.1
     bgp log-neighbor-changes
     neighbor SPINE peer-group
     !
     address-family ipv4
     neighbor SPINE send-community both
     neighbor SPINE soft-reconfiguration inbound
     neighbor SPINE route-map TOR_IMPORT_SPINE in
     neighbor SPINE route-map TOR_EXPORT_SPINE out
     exit-address-family

    but should be

    router bgp 65111
     bgp router-id 1.1.1.1
     bgp log-neighbor-changes
     neighbor SPINE peer-group
     !
     address-family ipv4
      neighbor SPINE send-community both
      neighbor SPINE soft-reconfiguration inbound
      neighbor SPINE route-map TOR_IMPORT_SPINE in
      neighbor SPINE route-map TOR_EXPORT_SPINE out
     exit-address-family

    The diff_logic func do it before make diff.
    """
    corrected_old = _create_subsections(old, "address-family")

    yield from common.default_diff(corrected_old, new, diff_pre, _pops)


def _create_subsections(data: OrderedDict[str, Any], sub_section_prefix: str) -> OrderedDict[str, Any]:
    """
    Reorganizes the given OrderedDict to nest commands under their respective
    sub_section_prefix keys.

    This function traverses the entries in the provided OrderedDict and groups
    together all entries that are between keys with sub_section_prefix under those
    keys as nested OrderedDicts. The reorganization keeps the order of entries
    stable, only adding nesting where appropriate.

    Args:
        data (OrderedDict): The original configuration to be transformed.
        sub_section_prefix (str): Prefix of subsection key

    Returns:
        OrderedDict: A new OrderedDict with nested 'address-family' sections.
    """

    result = OrderedDict()
    sub_section = None
    temp: OrderedDict = OrderedDict()

    for key, value in data.items():
        # make nested loop if found nested values
        if value:
            fixed_value: OrderedDict[str, Any] = _create_subsections(value, sub_section_prefix)
        else:
            fixed_value = value
        if key.startswith(sub_section_prefix):
            # in case of data has already had subsections
            if value:
                result[key] = fixed_value
                continue
            # if previous subsection present save collected data from temporary dict
            if sub_section:
                result[sub_section] = temp
            # find a new subsection and initialize new dict
            sub_section = key
            temp = OrderedDict()
        # put found data to temporary dict
        elif sub_section:
            temp[key] = fixed_value
        else:
            result[key] = fixed_value
    # if data is finished save collected data from temporary dict
    if sub_section:
        result[sub_section] = temp

    return result
