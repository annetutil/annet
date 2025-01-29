from annet.annlib.types import Op

from annet.rulebook import common


def mtu(old, new, diff_pre, **_):
    """
    Для того, чтобы удалить NTP из CFS, сначала нужно сбросить активные
    NTP сессии.
    """
    if diff[Op.REMOVED]:
        yield (False, "no mtu", None)
    elif diff[Op.ADDED]:
        yield from common.default(rule, key, diff)

