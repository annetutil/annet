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


# ?/{regex}/ and ~/{regex}/ let a row embed a raw regexp: ?/ matches without capturing,
# ~/ captures the whole match into a group. The regexp runs GREEDILY to the LAST / on the
# row, so it may contain anything (slashes, spaces) but a row may hold at most ONE such
# regexp placeholder -- put everything in a single regexp rather than chaining ?//~/.
# (This limit is only about ?//~/; * wildcards, */{regex}/, <name> groups and a trailing ~
# are independent and may repeat, e.g. `* * something ~`.)
# ~ may appear anywhere (it is not a regexp metachar). ? is a quantifier, so ?/ is only a
# placeholder at the row start or after whitespace.
_TILDE_PLACEHOLDER = re.compile(r"(~)/(.*)/")
_QMARK_PLACEHOLDER = re.compile(r"(?:^|(?<=\s))(\?)/(.*)/")

_SENTINEL = "\x00{}\x00"  # wraps the protected placeholder while the row is rewritten
_SENTINEL_RE = re.compile(r"\x00(\d+)\x00")


@functools.lru_cache()
def compile_row_regexp(row, flags=0):
    """Compile one ACL/rulebook row into a start-anchored regexp matching a config line:

    1. hide a ?/ or ~/ regexp placeholder behind a sentinel;
    2. expand * wildcards and <name> named groups;
    3. anchor the right edge with (?:\\s|$) unless the row already owns it;
    4. restore the placeholder.
    """
    if "(?i)" in row:
        row = row.replace("(?i)", "")
        flags |= re.IGNORECASE

    # 1. Protect the placeholder. The inner re.sub rewrites the user's own (groups) to
    #    non-capturing, so only the ~/ wrapper captures.
    protected: list[tuple[str, bool]] = []  # [(regexp, is_capturing)]

    def _hide(match: re.Match) -> str:
        regexp = re.sub(r"\(([^\?])", r"(?:\1", match.group(2))
        protected.append((regexp, match.group(1) == "~"))
        return _SENTINEL.format(len(protected) - 1)

    row = _TILDE_PLACEHOLDER.sub(_hide, row)
    row = _QMARK_PLACEHOLDER.sub(_hide, row)

    # 2. */{regex}/ and bare-* wildcards, then <name> named groups.
    if "*" in row:
        row = re.sub(r"\(([^\?])", r"(?:\1", row)  # default (groups) -> non-capturing
        row = re.sub(r"\*/(\S+)/", r"(\1)", row)  # */{one-word regexp}/ -> ({regexp})
        row = re.sub(r"(^|\s)\*", r"\1([^\\s]+)", row)  # bare * -> one word
    row = re.sub(r"<(\w+)>", r"(?P<\1>\\w+)", row)

    # 3. Anchor the right edge with (?:\s|$) so a row matches a whole token (interface Eth0
    #    must not match interface Eth01) -- unless the row's right EDGE is a regexp:
    #      foo~    capture the rest of the line (specificity resolved in match_row_to_acls)
    #      foo...  match a prefix and ignore the rest
    #      the row holds a placeholder (\x00 sentinel) AND ends in one, or ends in a )
    #        (a lookaround that nests a placeholder, e.g. interface (?!...|Vbdif(~/.../))).
    #        That regexp owns the edge, so the line may continue past the match (e.g. a
    #        subinterface 25GE1/0/10.1501 under ~/(25GE1\/0\/10(?![0-9]))/). A placeholder
    #        that is NOT at the edge does not count -- ~/x/ y still anchors the literal y --
    #        and a plain trailing group with no placeholder, (tacacs|default), stays
    #        anchored too.
    if row.endswith("~"):
        row = row[:-1] + "(.+)"
    elif row.endswith("..."):
        row = row[:-3]
    elif "\x00" in row and row.rstrip().endswith(("\x00", ")")):
        pass
    else:
        row += r"(?:\s|$)"

    # 4. Collapse whitespace runs, then restore the placeholder (after this step, so a
    #    regexp's own spaces survive as literal spaces).
    row = re.sub(r"\s+", r"\\s+", row)

    def _restore(match: re.Match) -> str:
        regexp, captures = protected[int(match.group(1))]
        return f"({regexp})" if captures else f"(?:{regexp})"

    row = _SENTINEL_RE.sub(_restore, row)
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
