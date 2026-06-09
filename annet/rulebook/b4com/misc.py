from annet.annlib.types import Op
from annet.rulebook import common


def undo_username(rule, key, diff, **kwargs):
    if diff[Op.REMOVED]:
        unchanged = kwargs["rule_pre"]["items"][key]["unchanged"]
        added = kwargs["rule_pre"]["items"][key]["added"]
        if not unchanged and not added:
            yield (False, f"no username {key[0]}", None)
        else:
            removed_diff = diff[Op.REMOVED][0]["row"]
            if "sshkey" in removed_diff:
                yield (False, f"no username {key[0]} sshkey {removed_diff.split('ssh-rsa')[-1]}", None)
                return
            yield from common.default(rule, key, diff)
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


def undo_snmp_cmnt(rule, key, diff, **kwargs):
    if diff[Op.REMOVED]:
        parts = key[0].split()
        community = parts[0]
        vrf = parts[-1]
        if "vrf" in key[0]:
            yield (False, f"no snmp-server community {community} vrf {vrf}", None)
        else:
            yield (False, f"no snmp-server community {community}", None)
    else:
        yield from common.default(rule, key, diff, **kwargs)
