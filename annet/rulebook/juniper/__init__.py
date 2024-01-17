import re
from collections import OrderedDict as odict
from functools import wraps

from annet.annlib.lib import jun_activate, jun_is_inactive, merge_dicts
from annet.annlib.types import Op

from annet.rulebook import common


def _inactive_blocks(diff_foo):
    @wraps(diff_foo)
    def wrapper(old, new, diff_pre, *args, **kwargs):
        old_inactives = list(map(jun_activate, filter(jun_is_inactive, old)))
        new_inactives = list(map(jun_activate, filter(jun_is_inactive, new)))
        if len(old_inactives) == 0 and len(new_inactives) == 0:
            return diff_foo(old, new, diff_pre, *args, **kwargs)

        inactive_pre = odict([(jun_activate(k), v) for k, v in diff_pre.items() if jun_is_inactive(k)])
        merged_pre = merge_dicts(diff_pre, inactive_pre)
        diff = diff_foo(_strip_toplevel_inactives(old),
                        _strip_toplevel_inactives(new),
                        merged_pre,
                        *args, **kwargs)

        for activated in [k for k in old_inactives if k in new]:
            diff += [(Op.ADDED, _activate_cmd(activated, merged_pre), {}, diff_pre[activated]["match"])]

        for deactivated in [k for k in new_inactives if k not in old_inactives]:
            # если деактивуруемого блока не существует - ставим один deactivate, глубже не идем
            if deactivated not in diff_pre:
                diff = [(Op.ADDED, _deactivate_cmd(deactivated, merged_pre), {}, inactive_pre[deactivated]["match"])]
            else:
                diff += [(Op.ADDED, _deactivate_cmd(deactivated, merged_pre), {}, diff_pre[deactivated]["match"])]
        return diff
    return wrapper


@_inactive_blocks
def default_diff(old, new, diff_pre, _pops=(Op.AFFECTED,)):
    diff = common.default_diff(old, new, diff_pre, _pops)
    diff = _ignore_quotes(diff)
    diff = _strip_inactive_removed(diff)
    return diff


@_inactive_blocks
def ordered_diff(old, new, diff_pre, _pops=(Op.AFFECTED,)):
    diff = common.ordered_diff(old, new, diff_pre, _pops)
    diff = _ignore_quotes(diff)
    diff = _strip_inactive_removed(diff)
    return diff


# =====
def _strip_toplevel_inactives(tree):
    for inactive in filter(jun_is_inactive, tree):
        assert jun_activate(inactive) not in tree
    return odict([(k, v) if not jun_is_inactive(k) else (jun_activate(k), v) for k, v in tree.items()])


def _activate_cmd(active_key, diff_pre):
    return _cmd(active_key, diff_pre, "activate")


def _deactivate_cmd(active_key, diff_pre):
    return _cmd(active_key, diff_pre, "deactivate")


def _cmd(active_key, diff_pre, cmd):
    assert not jun_is_inactive(active_key)
    if not diff_pre[active_key]["subtree"]:
        # Если конанда не имеет подблоков И имеет агрументы то надо их отбросить
        return " ".join([cmd, active_key.split()[0]])
    return " ".join([cmd, active_key])


def _ignore_quotes(diff):
    """
    Фильтрует из diff строки которые различаются
    только наличием/отсутсвием кавычек
    i.e.
    description "loopbacks";
    description loopbacks;
    эквивалентны
    """
    equivs = {}
    for elem in diff:
        key = _strip_quotes(elem[1])
        if key not in equivs:
            equivs[key] = 0
        equivs[key] += 1
    filtered_diff = [elem for elem in diff if equivs[_strip_quotes(elem[1])] == 1]
    return filtered_diff


def _strip_quotes(key):
    return re.sub(r"\"(?P<quoted_text>[^\"]+)\"$", r"\g<quoted_text>", key)


def _strip_inactive_removed(diff):
    for elem in diff:
        if elem[0] == Op.REMOVED and elem[3]["key"]:
            key = elem[3]["key"][0]
            if jun_is_inactive(key):
                elem[3]["key"] = tuple([jun_activate(key)])
    return diff
