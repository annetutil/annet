from annet.annlib.types import Op
from annet.rulebook import common


def undo_username(rule, key, diff, **_):
    if diff[Op.REMOVED]:
        yield (False, f"no username {key[0]}", None)
    else:
        yield from common.default(rule, key, diff)


def undo_syslog(rule, key, diff, **kwargs):
    if diff[Op.REMOVED]:
        parts = key[1].split()
        ip = parts[0]
        vrf = parts[-1]
        if "vrf" in key[1]:
            yield (False, f"no logging remote server {ip} vrf {vrf}", None)
        else:
            yield (False, f"no logging remote server {ip}", None)
    else:
        yield from common.default(rule, key, diff, **kwargs)
