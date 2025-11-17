from annet.annlib.types import Op


def undo_peer_group(rule, key, diff, **_):
    """Correctly removes neighbors that were added to the peer-group."""
    for action in diff[Op.ADDED]:
        yield (True, action["row"], None)

    if diff[Op.REMOVED]:

        is_group = any(action["row"].endswith(" peer-group") for action in diff[Op.REMOVED])

        group_name = ""
        for action in diff[Op.REMOVED]:
            if " peer-group " in action["row"]:
                group_name = action["row"].split()[-1]
        is_remote_as = any(" remote-as " in action["row"] for action in diff[Op.REMOVED])

        is_group_in_removed = False
        if _["rule_pre"]["items"].get(tuple([group_name])):
            for action in _["rule_pre"]["items"][tuple([group_name])]["removed"]:
                if action["row"].endswith(f"{group_name} peer-group"):
                    is_group_in_removed = True
                    break

        for action in diff[Op.REMOVED]:
            row = action["row"]
            if is_group:
                if row.endswith(" peer-group"):
                    yield (False, "no " + row, None)
            elif is_group_in_removed:
                continue
            elif is_remote_as or group_name:
                if " peer-group " in row:
                    yield (False, "no " + row, None)
            else:
                yield (False, "no " + row, None)
