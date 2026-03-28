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
    """
    If we remove a neighbor, we just remove configuration with remote-as command
    (+ peer-group if it's a group) but if we remove specific neighbor's options,
    without neighbor deletion we need check if neighbor * remote-as not exists
    in Op.REMOVED rule_pre items. Also we should check if neighbor's group will
    remove, no gen same for neighbor.
    """
    if diff[Op.REMOVED]:
        if "remote-as" in diff[Op.REMOVED][0]["row"]:
            neighbor = diff[Op.REMOVED][0]["row"].split()[1]
            # If neighbor's group under deletion, do not generate neighbor deletion
            if is_ipaddress(neighbor):
                neighbor_group = ""
                groups_for_deletion = []
                for item in kwargs["rule_pre"]["items"].values():
                    if item[Op.REMOVED]:
                        if f"{neighbor} peer-group" in item[Op.REMOVED][0]["row"]:
                            neighbor_group = item[Op.REMOVED][0]["row"].split()[-1]
                        if "remote-as" in item[Op.REMOVED][0]["row"]:
                            n = item[Op.REMOVED][0]["row"].split()[1]
                            if not is_ipaddress(n):
                                groups_for_deletion.append(n)
                if neighbor_group not in groups_for_deletion:
                    yield from common.default(rule, key, diff, **kwargs)
            else:
                yield (False, f"no neighbor {neighbor} remote-as", None)
                yield (False, f"no neighbor {neighbor} peer-group", None)
        else:
            is_neighbor_removing = False
            for item in kwargs["rule_pre"]["items"].values():
                if item[Op.REMOVED]:
                    if (
                        f"neighbor {key[0].split()[0]} remote-as"
                        in item[Op.REMOVED][0]["row"]
                    ):
                        is_neighbor_removing = True
                        break
            if not is_neighbor_removing:
                yield from common.default(rule, key, diff, **kwargs)
    else:
        yield from common.default(rule, key, diff, **kwargs)
