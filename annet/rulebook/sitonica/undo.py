import copy
import re

from annet.annlib.types import Op
from annet.rulebook import common


def two(rule, key, diff, **kwargs):
    """Undo commands that require two first parameters

    This command can't be undone with * or ~:
    network 2001:DB8:1:: 64 route-policy TO_HELL
    doesn't work:
    undo network 2001:DB8:1:: 64 route-policy TO_HELL

    Proper undo command is(2 params):
    undo network 2001:DB8:1:: 64
    """
    if diff[Op.REMOVED]:
        yield (False, "undo " + " ".join(diff[Op.REMOVED][0]["row"].split()[:3]), None)
    else:
        yield from common.default(rule, key, diff, **kwargs)


def strange(rule, key, diff, **kwargs):
    """Undo strange commands

    This list of commands can't be undone with standart methods:
    command -> undo command
    balance 64             -> undo balance
    balance as-path-relax  -> undo balance as-path-relax
    balance ebgp 4         -> undo balance ebgp
    """
    if diff[Op.REMOVED]:
        cmd = diff[Op.REMOVED][0]["row"]
        if cmd.startswith("balance "):
            if cmd.split()[1].isdigit():
                yield (False, "undo balance", None)
            else:
                yield (False, "undo " + " ".join(cmd.split()[:2]), None)
    else:
        yield from common.default(rule, key, diff, **kwargs)
