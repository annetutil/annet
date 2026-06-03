from __future__ import annotations

import functools
import re
from collections import OrderedDict as odict
from collections.abc import Iterator
from typing import Any, TypedDict, cast

from annet.annlib import lib
from annet.rulebook.types import ParamsScheme, RawParams, RawRow, Row
from annet.vendors import tabparser


# =====
def _merge_trees(t1: odict[Any, Any], t2: odict[Any, Any]) -> odict[Any, Any]:
    if not t1:
        return t2
    if not t2:
        return t1
    ret = t1.copy()
    for k, v in t2.items():
        if k in ret:
            ret[k]["children"] = _merge_trees(ret[k]["children"], v["children"])
        else:
            ret[k] = v
    return ret


def _convert(tree: ParsedTree) -> odict[Any, Any]:
    ret: odict[Any, Any] = odict()
    for rule_id, attrs in tree:
        if rule_id not in ret:
            ret[rule_id] = attrs | {"children": odict()}
        ret[rule_id]["children"] = _merge_trees(ret[rule_id]["children"], _convert(attrs["children"]))
    return ret


def parse_text(text: str, params_scheme) -> odict[Any, Any]:
    ret = _parse_tree_with_params(tabparser.parse_to_tree_multi(text, _split_rows, ["#"]), params_scheme)
    return _convert(ret)


class _ParsedTreeNode(TypedDict):
    row: str
    type: str
    params: dict[str, Any]
    children: ParsedTree
    raw_rule: str
    context: Any


ParsedTree = list[tuple[str, _ParsedTreeNode]]


def parse_text_multi(text: str, params_scheme) -> ParsedTree:
    ret = _parse_tree_with_params(tabparser.parse_to_tree_multi(text, _split_rows, ["#"]), params_scheme)
    return ret


@functools.lru_cache()
def compile_row_regexp(row, flags=0):
    if "(?i)" in row:
        row = row.replace("(?i)", "")
        flags |= re.IGNORECASE

    # ?/{regex}/ -> (?:{regex}), a non-capturing match against an arbitrary regexp.
    # Unlike */{regex}/ (which captures a single word) and ~/{regex}/, nothing is
    # captured into a group. The regexp is protected from the placeholder
    # substitutions below, i.e. *, (...) inside it stay part of the regexp instead
    # of being treated as placeholders. The ? prefix is glued to the /, so this
    # form does not clash with literal slashes (e.g. in interface names like
    # Eth0/0/1) nor with the */{regex}/ and ~/{regex}/ forms. The first / after
    # ?/ closes the placeholder, so the regexp itself cannot contain a literal /.
    protected: list[str] = []

    def _protect(match: re.Match) -> str:
        # Turn the default groups inside the regexp into non-capturing ones, so the
        # ?/{regex}/ form only matches and captures nothing.
        regexp = re.sub(r"\(([^\?])", r"(?:\1", match.group(1))
        protected.append(regexp)
        return f"\x00{len(protected) - 1}\x00"

    row = re.sub(r"(?:^|(?<=\s))\?/([^/]+)/", _protect, row)

    if "*" in row:
        row = re.sub(r"\(([^\?])", r"(?:\1", row)  # Все дефолтные группы превратить в non-captured
        row = re.sub(r"\*/(\S+)/", r"(\1)", row)  # */{regex_one_word}/ -> ({regex_one_word})
        row = re.sub(r"(^|\s)\*", r"\1([^\\s]+)", row)

    # Заменяем <someting> на named-группы
    row = re.sub(r"<(\w+)>", r"(?P<\1>\\w+)", row)

    if row.endswith("~"):
        # We determine the most specific regex for the row at matching in match_row_to_acls
        row = row[:-1] + "(.+)"
    elif row.endswith("..."):
        row = row[:-3]
    elif "~/" in row:
        # ~/{regex}/ -> (?:{regex}), a non-capturing match. The first / after ~/
        # closes the placeholder (so the regexp cannot contain a literal /), and the
        # (?:) wrap keeps a top-level alternation (a|b) from leaking into the rest of
        # the row.
        row = re.sub(r"~/([^/]+)/", r"(?:\1)", row)
    else:
        row += r"(?:\s|$)"
    row = re.sub(r"\s+", r"\\s+", row)
    if protected:
        row = re.sub(r"\x00(\d+)\x00", lambda m: f"(?:{protected[int(m.group(1))]})", row)
    return re.compile("^" + row, flags=flags)


# =====
def _split_rows(text: str) -> Iterator[str]:
    for row in re.split(r"\n(?!\s*%(?!context))", text):
        yield row.replace("\n", " ")


def _parse_tree_with_params(raw_tree: tabparser.SimpleTree, scheme, context: dict | None = None) -> ParsedTree:
    tree: ParsedTree = []
    if context is None:
        context = {}
    for raw_rule, children in raw_tree:
        (row, params) = parse_raw_rule(raw_rule, scheme)
        row_type = "normal"

        if row.startswith("!"):
            row = row[1:].strip()
            if len(row) == 0:
                continue
            row_type = "ignore"
        elif context_raw := params.get("context"):
            context = _parse_context(context, context_raw)
            continue
        tree.append(
            (
                raw_rule,
                {
                    "row": row,
                    "type": row_type,
                    "params": params,
                    "children": _parse_tree_with_params(children, scheme, cast(dict, context).copy()),
                    "raw_rule": raw_rule,
                    "context": cast(dict, context).copy(),
                },
            )
        )
    return tree


def parse_raw_rule(raw_rule: str, scheme) -> tuple[str, dict[str, str]]:
    params: dict[str, str] = {}

    row, *params_raw = re.split(r"(?:^|\s)%(?=[a-zA-Z_]\w*)", raw_rule)
    for param in params_raw:
        name, _, value = param.partition("=")
        params[name.strip()] = value.strip() or "1"

    row = re.sub(r"\s+", " ", row.strip())
    params = _fill_and_validate(params, scheme, raw_rule)
    return row, params


def _fill_and_validate(params, scheme, raw_rule):
    return {
        key: (
            attrs["validator"](params[key])
            if key in params
            else (attrs["default"](raw_rule) if callable(attrs["default"]) else attrs["default"])
        )
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
    name, value = row.strip().split(":")
    return lib.merge_dicts(context, {name: value})


def get_row_and_raw_params(raw_row: RawRow) -> tuple[Row, RawParams]:
    """Parses a raw rule string, returning the rule string without params and the raw params"""
    params = {}
    row, *raw_params = re.split(r"(?:^|\s)%(?=[a-zA-Z_]\w*)", raw_row)
    for param in raw_params:
        name, _, value = param.partition("=")
        params[name.strip()] = value.strip()
    row = re.sub(r"\s+", " ", row.strip())
    return row, params


def get_row_with_params(row: Row, params: RawParams, params_scheme: ParamsScheme) -> RawRow:
    """Joins a rule string without params and raw params, returning the raw rule string"""
    params = clean_params_by_params_scheme(params, params_scheme)
    params = strip_default_params_by_params_scheme(params, params_scheme)
    params_line: str = " ".join([f"%{k}={v}" if v else f"%{k}" for k, v in params.items()])
    return f"{row} {params_line}" if params_line else row


def clean_params_by_params_scheme(params: RawParams, params_scheme: ParamsScheme) -> RawParams:
    """Remove parameters from 'params' not present in 'params_scheme'"""
    return {name: value for name, value in params.items() if name in params_scheme}


def strip_default_params_by_params_scheme(params: RawParams, params_scheme: ParamsScheme) -> RawParams:
    """Remove parameters with default value from 'params'"""
    result_params = {}
    for name, value in params.items():
        validator = params_scheme[name]["validator"]
        default = params_scheme[name]["default"]
        if validator(value if value != "" else "1") != default:
            result_params[name] = value
    return result_params
