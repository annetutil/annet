from annet.annlib.rulebook import common
from annet.annlib.types import Op


def default_diff(old, new, diff_pre, _pops=(Op.AFFECTED,)):
    diff = common.default_diff(old, new, diff_pre, _pops)
    return diff


def ordered_diff(old, new, diff_pre, _pops=(Op.AFFECTED,)):
    diff = common.ordered_diff(old, new, diff_pre, _pops)
    return diff
