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
        current_row = diff[Op.REMOVED][0]["row"]
        peer = current_row.split()[1]
        
        is_peer_deleted = False
        is_peer_disabled = False
        for item in kwargs["rule_pre"]["items"].values():
            if item[Op.REMOVED]:
                if is_ipaddress(peer):
                    if " as-number " in item[Op.REMOVED][0]["row"]:
                        is_peer_deleted = True
                        break
                    if " group " in item[Op.REMOVED][0]["row"]:
                        is_peer_deleted = True
                        break
                else:
                    if "group " in item[Op.REMOVED][0]["row"]:
                        is_peer_deleted = True
                        break
                if " enable" in item[Op.REMOVED][0]["row"]:
                    is_peer_disabled = True
                    break

        if is_peer_deleted:
            if is_ipaddress(peer):
                yield (False, f"undo peer {peer}", None)
            else:
                if current_row.startswith("group "):
                    yield (False, f"undo group {peer}", None)
                else:
                    return
        elif is_peer_disabled:
            yield (False, f"undo peer {peer} enable", None)
        else:
            if (
                (" description " in current_row)
                or (" connect-interface " in current_row)
                or (" fake-as " in current_row)
                or (" route-update-interval " in current_row)
                or (" bfd " in current_row)
                # address-family options
                or " route-limit " in current_row
            ):
                yield (False, f"undo {' '.join(current_row.split()[:3])}", None)
            elif (
                " bmp server " in current_row
            ):
                yield (False, f"undo {' '.join(current_row.split()[:4])}", None)
            else:
                yield from common.default(rule, key, diff, **kwargs)

    else:
        yield from common.default(rule, key, diff, **kwargs)