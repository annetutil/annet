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
        neighbor = diff[Op.REMOVED][0]["row"].split()[1]
        is_neighbor_removing = False
        for item in kwargs["rule_pre"]["items"].values():
            if item[Op.REMOVED]:
                if "as-number" in item[Op.REMOVED][0]["row"]:
                    is_neighbor_removing = True

        if is_neighbor_removing:
            yield (False, f"undo peer {neighbor}", None)
        else:
            yield from common.default(rule, key, diff, **kwargs)
    else:
        yield from common.default(rule, key, diff, **kwargs)