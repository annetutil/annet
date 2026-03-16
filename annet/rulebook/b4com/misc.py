from annet.annlib.types import Op
from annet.rulebook import common


def undo_username(rule, key, diff, **_):
    if diff[Op.REMOVED]:
        yield (False, f"no username {key[0]}", None)
    else:
        yield from common.default(rule, key, diff)