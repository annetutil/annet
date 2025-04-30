from annet.annlib.types import Op

from annet.rulebook import common


def mtu(rule, key, diff, **kwargs):
    """
    Удаляем mtu без указания значения
    """
    if diff[Op.REMOVED]:
        yield (False, "no mtu", None)
    elif diff[Op.ADDED]:
        yield from common.default(rule, key, diff, **kwargs)


def description(rule, key, diff, **kwargs):
    """
    Удаляем description без указания значения
    """
    if diff[Op.REMOVED]:
        yield (False, "no description", None)
    elif diff[Op.ADDED]:
        yield from common.default(rule, key, diff, **kwargs)


def sflow(rule, key, diff, **kwargs):
    """
    Команда sflow sampling-rate * direction ingress max-header-size *
    сносится без указания sampling-rate и max-header-size
    """
    result = common.default(rule, key, diff, **kwargs)
    for op, cmd, ch in result:
        if diff[Op.REMOVED]:
            if "ingress" in diff[Op.REMOVED][0]["row"]:
                yield (op, "no sflow sampling-rate direction ingress", ch)
            elif "egress" in diff[Op.REMOVED][0]["row"]:
                yield (op, "no sflow sampling-rate direction egress", ch)
            else:
                yield (op, cmd, ch)
    return result


def lldp(rule, key, diff, **kwargs):
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
