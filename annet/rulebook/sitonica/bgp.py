from ipaddress import ip_address

from annet.annlib.types import Op
from annet.rulebook import common


def is_ipaddress(address: str) -> bool:
    try:
        ip_address(address)
        return True
    except ValueError:
        return False


def undo_peer(rule, key, diff, **kwargs):
    if diff[Op.REMOVED]:
        # if "description" in diff[Op.REMOVED][0]["row"]:
        #     import ipdb; ipdb.set_trace()
        neighbor = diff[Op.REMOVED][0]["row"].split()[1]
        is_peer_deleted = False
        is_peer_disabled = False
        for item in kwargs["rule_pre"]["items"].values():
            if item[Op.REMOVED]:
                if " as-number " in item[Op.REMOVED][0]["row"]:
                    is_peer_deleted = True
                    break
                if " group " in item[Op.REMOVED][0]["row"]:
                    is_peer_deleted = True
                    break
                if " enable" in item[Op.REMOVED][0]["row"]:
                    is_peer_disabled = True
                    break

        if is_peer_deleted:
            yield (False, f"undo peer {neighbor}", None)
        elif is_peer_disabled:
            yield (False, f"undo peer {neighbor} enable", None)
        else:
            yield from common.default(rule, key, diff, **kwargs)
    else:
        yield from common.default(rule, key, diff, **kwargs)