import os
import typing
from collections import OrderedDict as odict

from annet.annlib.command import Command, CommandList
from annet.annlib.netdev.views.hardware import HardwareView
from annet.types import Op
from annet.vendors import registry_connector


# Op-keyed diff structure passed to patch-logic functions
DiffDict = dict[str, list[dict[str, typing.Any]]]
# Each patch-logic function yields (direct, row, sub_pre)
LogicResult = typing.Iterator[tuple[bool, str, typing.Any]]


# =====
def default(rule: dict[str, typing.Any], key: tuple[str, ...], diff: DiffDict, **_: typing.Any) -> LogicResult:
    r"""
    The default() function provides the basic processing logic for all rules. It can be replaced with the
    %logic parameter in the text rulebook. It is called for every command with a unique key and
    must return the generated patch text based on the supplied diff and, if necessary,
    trigger the processing of the child rules/data.

    Its first argument (rule) is a dict with the rule:
        {
            # A single-line command, not a block, has no children
            "logic": <function default at 0x7fe22ea83510>,  # the function that processes the rule
            "provides": [],  # macros provided by this rule
            "requires": [],  # macros required by this rule

            # regexp used to parse the row
            "regexp": re.compile(r"^snmp-agent\s+sys-info\s+([^\s]+).*$"),

            # template used to cancel the command (the key should be used as its arguments)
            "reverse": "undo snmp-agent sys-info {}",
        }

    The second argument (key) is a tuple made of the key parsed from the row with the regexp:
        ("contact",)  # example for parsing the row "snmp-agent sys-info contact"

    The third argument is a dict with the diff:
        {
            # commands/blocks added in the new configuration
            Op.ADDED: [{"children": None, "row": "undo snmp-agent sys-info version all"}],

            # only appears in blocks, holds the children that changed inside a block
            Op.AFFECTED: [],

            # removed commands/blocks
            Op.REMOVED: [{"children": None, "row": "undo snmp-agent sys-info version v3"}],

            # commands that have not changed at all (but are sometimes needed by other commands)
            Op.UNCHANGED: [{"children": None, "row": "snmp all-interfaces"}]
        }
    """
    for op in [Op.ADDED, Op.REMOVED, Op.AFFECTED, Op.MOVED]:
        # The default patch generation function assumes there are no commands with the same
        # key but a different value. The unchanged op is not checked this way though, since
        # such cases are possible when implicit commands are mixed in
        assert 0 <= len(diff[op]) <= 1, "Too many %s actions for rows %r" % (op, [x["row"] for x in diff[op]])
    if diff[Op.AFFECTED]:
        # When a block changes, the children have to be processed
        yield (True, diff[Op.AFFECTED][0]["row"], diff[Op.AFFECTED][0]["children"])
    elif diff[Op.ADDED] or diff[Op.MOVED]:
        op_key = Op.ADDED if diff.get(Op.ADDED) else Op.MOVED
        # When a row is modified we do not care about the removal; the addition goes through as affected
        yield (True, diff[op_key][0]["row"], diff[op_key][0]["children"])
    elif diff[Op.REMOVED]:
        # When a block is removed or moved, just drop the row
        yield (False, rule["reverse"].format(*key), None)


def ordered(rule: dict[str, typing.Any], key: tuple[str, ...], diff: DiffDict, **kwargs: typing.Any) -> LogicResult:
    if diff[Op.MOVED]:
        # Drop the top-level block
        yield (False, rule["reverse"].format(*key), None)
    # Op.MOVED items will be re-created below in the new order
    # FIXME strictly speaking REMOVED should be dropped from the children,
    # since the block is already cleared and is being re-created
    yield from default(rule, key, diff, **kwargs)


def rewrite(rule: dict[str, typing.Any], key: tuple[str, ...], diff: DiffDict, **kwargs: typing.Any) -> LogicResult:
    # Rewrites the block ignoring its previous state
    if not diff[Op.REMOVED]:
        yield from default(rule, key, diff, **kwargs)


def permanent(rule: dict[str, typing.Any], key: tuple[str, ...], diff: DiffDict, **kwargs: typing.Any) -> LogicResult:
    # This block must not be removed
    if diff[Op.REMOVED]:
        # If it stands alone - just ignore it
        if not diff[Op.REMOVED][0]["children"]:
            return
        # If it has children - mark them as affected
        diff[Op.AFFECTED] += diff[Op.REMOVED]
        diff[Op.REMOVED] = []
    yield from default(rule, key, diff, **kwargs)


def ignore_changes(
    rule: dict[str, typing.Any], key: tuple[str, ...], diff: DiffDict, **kwargs: typing.Any
) -> LogicResult:
    """
    A logic function that removes or adds rows, but never replaces one with another.
    """
    if diff[Op.ADDED] and diff[Op.REMOVED]:
        pass
    else:
        yield from default(rule, key, diff, **kwargs)


def undo_redo(rule: dict[str, typing.Any], key: tuple[str, ...], diff: DiffDict, **_: typing.Any) -> LogicResult:
    """
    If a command is cancelled with undo key but cannot be replaced with
    key value, and instead requires undo key first and only then key value,
    this helper does exactly that: undo key first, then key value
    """
    if not (diff[Op.ADDED] and diff[Op.REMOVED] and not diff[Op.AFFECTED]):
        yield from default(rule, key, diff)
    else:
        for side in [Op.REMOVED, Op.ADDED]:
            new_diff: dict[str, list[dict[str, typing.Any]]] = {op: [] for op in diff.keys()}
            new_diff[side] = diff[side]
            yield from default(rule, key, new_diff)


def default_instead_undo(
    rule: dict[str, typing.Any], key: tuple[str, ...], diff: DiffDict, **_: typing.Any
) -> LogicResult:
    # A number of configuration rows produce a permanent diff, because in the config a row is either explicitly enabled
    # or explicitly disabled. If it is not described in the generator, i.e. we rely on the default, then using default
    # instead of "no ..." returns the config to its default state.
    # NOC-20503 @lesnix 11-08-2022
    if diff[Op.REMOVED]:
        rule["reverse"] = rule["reverse"].replace("no", "default")
    yield from default(rule, key, diff)


# =====
class DiffItem(typing.NamedTuple):
    op: str
    row: str
    children: list["DiffItem"]
    diff_pre: dict[str, typing.Any]


Differ = typing.Callable[
    [odict[str, typing.Any], odict[str, typing.Any], odict[str, typing.Any], tuple[str, ...]], list[DiffItem]
]


def default_diff(
    old: odict[str, typing.Any],
    new: odict[str, typing.Any],
    diff_pre: odict[str, typing.Any],
    _pops: tuple[str, ...] = (Op.AFFECTED,),
) -> list[DiffItem]:
    diff = base_diff(old, new, diff_pre, _pops, moved_to_affected=True)
    return diff


def ordered_diff(
    old: odict[str, typing.Any],
    new: odict[str, typing.Any],
    diff_pre: odict[str, typing.Any],
    _pops: tuple[str, ...] = (Op.AFFECTED,),
) -> list[DiffItem]:
    diff = base_diff(old, new, diff_pre, _pops, moved_to_affected=False)
    return diff


def rewrite_diff(
    old: odict[str, typing.Any],
    new: odict[str, typing.Any],
    diff_pre: odict[str, typing.Any],
    _pops: tuple[str, ...] = (Op.AFFECTED,),
) -> list[DiffItem]:
    def iter_diff(diff: list[DiffItem]) -> typing.Iterable[tuple[int, list[DiffItem]]]:
        queue = [diff]
        while queue:
            items, queue = queue[0], queue[1:]
            for i, item in enumerate(items):
                yield i, items
                queue.append(item.children)

    # leave a marker so that we can tell we are the outermost rewrite
    rewrite_marker = "rewrite"
    rewrite_tail = (rewrite_marker, _pops[-1])
    _pops = _pops + rewrite_tail
    diff = base_diff(old, new, diff_pre, _pops, moved_to_affected=False)
    # if we are the top-level rewrite and everything in the subtree is Op.AFFECTED,
    # i.e. there were no changes at all, drop it from the diff
    if rewrite_marker not in _pops[: -len(rewrite_tail)]:
        if all(its[i].op == Op.AFFECTED for i, its in iter_diff(diff)):
            diff.clear()
        else:
            for i, items in iter_diff(diff):
                if items[i].op == Op.AFFECTED:
                    items[i] = items[i]._replace(op=Op.MOVED)
    return diff


def multiline_diff(
    old: odict[str, typing.Any],
    new: odict[str, typing.Any],
    diff_pre: odict[str, typing.Any],
    _pops: tuple[str, ...] = (Op.AFFECTED,),
) -> list[DiffItem]:
    """
    Special diff logic for huawei multilines.
    It treats all the children of a %multiline command as
    a single common command, pushing down the Op that was
    determined at the top level
    """

    def process_multiline(
        op: str, tree: odict[str, typing.Any]
    ) -> typing.Iterator[tuple[str, str, list[typing.Any], None]]:
        for row, children in tree.items():
            yield op, row, list(process_multiline(op, children)), None

    ret = []
    for item in default_diff(old, new, diff_pre, _pops):
        if old.get(item.row, {}) == new.get(item.row, {}):
            continue
        op, tree = Op.ADDED, new
        if item.op == Op.REMOVED:
            op, tree = Op.REMOVED, old
        # multiline treats children as "raw" tuples rather than DiffItem
        children = typing.cast("list[DiffItem]", list(process_multiline(op, tree[item.row])))
        ret.append(DiffItem(item.op, item.row, children, item.diff_pre))

    return ret


def base_diff(
    old: odict[str, typing.Any],
    new: odict[str, typing.Any],
    diff_pre: odict[str, typing.Any],
    pops: tuple[str, ...],
    moved_to_affected: bool = False,
) -> list[DiffItem]:
    diff_indexed: list[tuple[int, DiffItem]] = []
    old = _ignore_case(diff_pre, old)
    new = _ignore_case(diff_pre, new)

    for index, row in enumerate(old):
        if row not in new:
            children = call_diff_logic(diff_pre[row]["subtree"], old[row], odict(), pops + (Op.REMOVED,))
            diff_indexed.append(
                (
                    index,
                    DiffItem(
                        op=Op.REMOVED,
                        row=row,
                        children=children,
                        diff_pre=diff_pre[row]["match"],
                    ),
                )
            )

    old_indexes = {row: index for (index, row) in enumerate(old)}
    block_in_disorder = False
    parent_op = pops[-1]
    for index, row in enumerate(new):
        if row not in old:
            block_in_disorder = True
            op = Op.ADDED
        elif block_in_disorder or index != old_indexes[row]:
            block_in_disorder = True
            op = Op.MOVED if not moved_to_affected else parent_op
        else:
            op = parent_op
        children = call_diff_logic(diff_pre[row]["subtree"], old.get(row, {}), new[row], pops + (op,))
        diff_indexed.append(
            (
                index,
                DiffItem(
                    op=op,
                    row=row,
                    children=children,
                    diff_pre=diff_pre[row]["match"],
                ),
            )
        )
    diff_indexed.sort()
    return [x[1] for x in diff_indexed]


def call_diff_logic(
    diff_pre: odict[str, typing.Any],
    old: odict[str, typing.Any],
    new: odict[str, typing.Any],
    pops: tuple[str, ...] = (Op.AFFECTED,),
) -> list[DiffItem]:
    """
    Group the commands in the old and the new config according to the %diff_logic
    attributes set in the rulebook and call each logic in turn, then
    stitch the results back together in the order of the commands in old and new, preferring
    old (i.e. removals come first)
    """
    diff_logics: odict[typing.Any, typing.Any] = odict()
    for row in old:
        logic = diff_pre[row]["match"]["attrs"]["diff_logic"]
        if logic not in diff_logics:
            diff_logics[logic] = (odict(), odict())
        diff_logics[logic][0][row] = old[row]
    for row in new:
        logic = diff_pre[row]["match"]["attrs"]["diff_logic"]
        if logic not in diff_logics:
            diff_logics[logic] = (odict(), odict())
        diff_logics[logic][1][row] = new[row]

    if len(diff_logics) == 1:
        ((logic, (logic_old, logic_new)),) = diff_logics.items()
        return list(logic(old=logic_old, new=logic_new, diff_pre=diff_pre, _pops=pops))

    positions = _row_positions(old, new)
    indexed: list[tuple[int, DiffItem]] = []
    for logic, (logic_old, logic_new) in diff_logics.items():
        position = 0
        for item in logic(old=logic_old, new=logic_new, diff_pre=diff_pre, _pops=pops):
            position = positions.get(item.row, position)
            indexed.append((position, item))
    indexed.sort(key=lambda pair: pair[0])
    return [item for _, item in indexed]


def _row_positions(old: odict[str, typing.Any], new: odict[str, typing.Any]) -> dict[str, int]:
    positions: dict[str, int] = {}
    for index, row in enumerate(old):
        if row not in new:
            positions[row] = index
    for index, row in enumerate(new):
        positions[row] = index
    for row, index in list(positions.items()):
        positions.setdefault(row.lower(), index)
    return positions


def _ignore_case(diff_pre: odict[str, typing.Any], cfg: odict[str, typing.Any]) -> odict[str, typing.Any]:
    has_ignore_case = False
    for row in diff_pre:
        if diff_pre[row]["match"]["attrs"]["ignore_case"]:
            has_ignore_case = True
    if not has_ignore_case:
        return cfg

    ret = cfg.__class__()
    for row in cfg:
        new_row = row
        if diff_pre[row]["match"]["attrs"]["ignore_case"]:
            new_row = row.lower()
        ret[new_row] = cfg[row]
        diff_pre[new_row] = diff_pre[row]
    return ret


# ====


class ApplyItem(typing.NamedTuple):
    before: CommandList
    after: CommandList


def apply(hw: HardwareView, do_commit: bool, do_finalize: bool, path: str | None) -> tuple[CommandList, CommandList]:
    return registry_connector.get().match(hw).apply(hw, do_commit, do_finalize, path)
