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
