import ipaddress
from collections.abc import Generator

import colorama

from ..types import Diff, DiffItem, Op


# NOCDEV-1720


diff_ops: dict[str, Op] = {
    "+": Op.ADDED,
    "-": Op.REMOVED,
    " ": Op.AFFECTED,
    ">": Op.MOVED,
}

ops_sign = {v: k for k, v in diff_ops.items()}

ops_order: dict[Op, int] = {
    Op.AFFECTED: 0,
    Op.REMOVED: 1,
    Op.ADDED: 2,
    Op.MOVED: 4,
}

ops_color: dict[Op, int] = {
    Op.REMOVED: colorama.Fore.RED,
    Op.ADDED: colorama.Fore.GREEN,
    Op.AFFECTED: colorama.Fore.CYAN,
    Op.MOVED: colorama.Fore.YELLOW,
}


def is_int(ts: str) -> bool:
    try:
        int(ts)
        return True
    except ValueError:
        return False


def is_ip(ts: str) -> bool:
    try:
        ipaddress.ip_interface(ts)
        return True
    except ValueError:
        return False


def diff_cmp(
    diff_l: DiffItem,
    diff_r: DiffItem,
) -> int:
    key_l = diff_sort_key(diff_l)
    key_r = diff_sort_key(diff_r)
    return (key_l > key_r) - (key_l < key_r)


def diff_sort_key(diff_line: DiffItem) -> tuple[int, int]:
    op, line, _, _ = diff_line

    op_key = ops_order[op]

    value = 0
    for word in line.split(" ")[:2]:
        if is_int(word):
            value = int(word)
            break
        elif is_ip(word):
            ip = ipaddress.ip_interface(word)
            if ip.version == 4:
                value = 2**32 - int(ip)
            else:
                value = +int(ip)
            break

    return value, op_key


def resort_diff(diff: Diff) -> Diff:
    res = []
    df = sorted(diff, key=diff_sort_key)
    for line in df:
        ln = line
        if len(line[2]) > 0:
            ln = (line[0], line[1], resort_diff(line[2]), line[3])
        res.append(ln)
    return res


def colorize_line_with_color(line: str, color: int, no_color: bool) -> str:
    stripped = line.rstrip("\n")
    add_newlines = len(line) - len(stripped)
    line = stripped

    if not no_color:
        line = "%s%s%s%s" % (colorama.Style.BRIGHT, color, line, colorama.Style.RESET_ALL)

    line += "\n" * add_newlines
    return line


def colorize_line(line: str, no_color: bool = False) -> str:
    op = diff_ops[line[0]]
    color = ops_color[op]
    return colorize_line_with_color(line, color, no_color)


def gen_pre_as_diff(
    pre: dict, show_rules: bool, indent: str, no_color: bool, _level: int = 0
) -> Generator[str, None, None]:
    ops = [(order, op) for op, order in ops_order.items()]
    ops.sort()

    for raw_rule, content in pre.items():
        items = content["items"].items()
        for _, diff in items:  # pylint: disable=redefined-outer-name
            if show_rules and not raw_rule == "__MULTILINE_BODY__":
                line = "# %s%s\n" % (indent * _level, raw_rule)
                yield colorize_line_with_color(line, colorama.Fore.BLACK, no_color)

            for op, rows in [(op, diff[op]) for (_, op) in ops]:
                for item in rows:
                    line = "%s%s %s\n" % (ops_sign[op], indent * _level, item["row"])
                    yield colorize_line_with_color(line, ops_color[op], no_color)
                    if len(item["children"]) != 0:
                        yield from gen_pre_as_diff(item["children"], show_rules, indent, no_color, _level + 1)
