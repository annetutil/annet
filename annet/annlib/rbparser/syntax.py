import functools
import re
from collections import OrderedDict as odict

from annet.annlib import lib, tabparser


# =====
def parse_text(text, params_scheme):
    return _parse_tree_with_params(tabparser.parse_to_tree(text, _split_rows, ["#"]), params_scheme)


@functools.lru_cache()
def compile_row_regexp(row, flags=0):
    if "(?i)" in row:
        row = row.replace("(?i)", "")
        flags |= re.IGNORECASE

    if "*" in row:
        row = re.sub(r"\(([^\?])", r"(?:\1", row)  # Все дефолтные группы превратить в non-captured
        row = re.sub(r"\*/(\S+)/", r"(\1)", row)   # */{regex_one_word}/ -> ({regex_one_word})
        row = re.sub(r"(^|\s)\*", r"\1([^\\s]+)", row)

    # Заменяем <someting> на named-группы
    row = re.sub(r"<(\w+)>", r"(?P<\1>\\w+)", row)

    if row.endswith("~"):
        # We determine the most specific regex for the row at matching in match_row_to_acls
        row = row[:-1] + "(.+)"
    elif row.endswith("..."):
        row = row[:-3]
    elif "~/" in row:
        # ~/{regex}/ -> {regex}, () не нужны поскольку уже (?:) - non-captured
        row = re.sub(r"~/(((?!~/).)+)/", r"\1", row)
    else:
        row += r"(?:\s|$)"
    row = re.sub(r"\s+", r"\\s+", row)
    return re.compile("^" + row, flags=flags)


# =====
def _split_rows(text):
    for row in re.split(r"\n(?!\s*%(?!context))", text):
        yield row.replace("\n", " ")


def _parse_tree_with_params(raw_tree, scheme, context=None):
    tree = odict()
    if context is None:
        context = {}
    for (raw_rule, children) in raw_tree.items():
        (row, params) = _parse_raw_rule(raw_rule, scheme)
        row_type = "normal"
        if row.startswith("!"):
            row = row[1:].strip()
            if len(row) == 0:
                continue
            row_type = "ignore"
        elif row.startswith(r"%context="):
            context = _parse_context(context, row)
            continue
        tree[raw_rule] = {
            "row": row,
            "type": row_type,
            "params": params,
            "children": _parse_tree_with_params(children, scheme, context.copy()),
            "raw_rule": raw_rule,
            "context": context.copy(),
        }
    return tree


def _parse_raw_rule(raw_rule, scheme):
    try:
        index = raw_rule.index("%")
        params = {
            key: (value if len(value) != 0 else "1")
            for (key, value) in re.findall(r"\s%([a-zA-Z_]\w*)(?:=([^\s]*))?", raw_rule)
        }
        if params:
            raw_rule = raw_rule[:index].strip()
    except ValueError:
        params = {}

    row = re.sub(r"\s+", " ", raw_rule.strip())
    params = _fill_and_validate(params, scheme, raw_rule)
    return (row, params)


def _fill_and_validate(params, scheme, raw_rule):
    return {
        key: (attrs["validator"](params[key]) if key in params else (
            attrs["default"](raw_rule) if callable(attrs["default"]) else attrs["default"]
        ))
        for (key, attrs) in scheme.items()
    }


def match_context(ifcontext, context):
    if not ifcontext:
        return True
    for ifcontext_value in ifcontext:
        name, value = ifcontext_value.split(":")
        if name in context:
            if context[name] == value:
                return True
    return False


def _parse_context(context, row):
    keyword = r"%context="
    if not row.startswith(keyword):
        raise ValueError(row)
    name, value = row[len(keyword):].strip().split(":")
    return lib.merge_dicts(context, {name: value})
