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


def _ends_with_zero_width(pat: str) -> bool:
    """True if ``pat`` ends with a top-level zero-width lookaround group -- (?!...),
    (?=...), (?<=...) or (?<!...) -- whose closing paren is the last character. Such a
    tail matches a zero-width span, so a (?:\\s|$) word-boundary anchor appended after
    it could never succeed. Escapes and [...] character classes are skipped so their
    parens are not miscounted."""
    pat = pat.rstrip()
    if not pat.endswith(")"):
        return False
    depth = 0
    in_class = False
    last_top_is_lookaround = False
    i = 0
    n = len(pat)
    while i < n:
        c = pat[i]
        if c == "\\":
            i += 2
            continue
        if in_class:
            if c == "]":
                in_class = False
        elif c == "[":
            in_class = True
        elif c == "(":
            if depth == 0:
                last_top_is_lookaround = pat[i : i + 3] in ("(?!", "(?=") or pat[i : i + 4] in ("(?<=", "(?<!")
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0 and i == n - 1:
                return last_top_is_lookaround
        i += 1
    return False


@functools.lru_cache()
def compile_row_regexp(row, flags=0):
    if "(?i)" in row:
        row = row.replace("(?i)", "")
        flags |= re.IGNORECASE

    # ?/{regex}/ and ~/{regex}/ both match an arbitrary regexp. ?/{regex}/ is a
    # non-capturing match (nothing reaches a group), while ~/{regex}/ captures its
    # whole matched span into a single group (like */{regex}/ but spanning more than
    # one word). Both are pulled out before the placeholder substitutions below so
    # that *, (...) inside the user's own regexp stay part of the regexp instead of
    # being reinterpreted, and so any groups the user wrote inside collapse to
    # non-capturing -- only the ~/ wrapper itself captures. The ? / ~ prefix is glued
    # to the /, so neither form clashes with literal slashes (e.g. interface names
    # like Eth0/0/1).
    #
    # The closing / is the first one followed by whitespace, or (lazily) by non-slash
    # text running up to the start of another ?/ or ~/ placeholder or end-of-row. This
    # lets the regexp itself embed literal slashes (~/(GE.+?/[12](\.|$))/ for names like
    # GE1/0/2), splits placeholders glued directly or via literal text -- e.g.
    # ~/(25GE.+?/[12])/.~/(\d+)/ mode l2 -- at their join, and still leaves trailing
    # literal text after a placeholder intact (~/interface|if/ eth0/1/2, ?/(.*)/permit).
    #
    # ~ is never a regexp metachar, so ~/ is matched anywhere -- including inside a
    # hand-written regexp like interface (?!Vbdif(~/(52\d{4})/)), where the generator
    # interpolates ~/.../ into a larger (?!...) expression. ? IS a quantifier, so ?/ is
    # only treated as a placeholder at the row start, after whitespace, or after one of
    # the structural chars "( ! = |" -- never after an atom it could be quantifying.
    protected: list[tuple[str, bool]] = []  # (regexp, captures)

    def _protect(match: re.Match) -> str:
        captures = match.group(1) == "~"
        regexp = re.sub(r"\(([^\?])", r"(?:\1", match.group(2))
        protected.append((regexp, captures))
        return f"\x00{len(protected) - 1}\x00"

    _close = r"/(?=\s|[^/]*?(?:[?~]/|$))"
    row = re.sub(r"(~)/(.+?)" + _close, _protect, row)
    row = re.sub(r"(?:^|(?<=[\s(!=|]))(\?)/(.+?)" + _close, _protect, row)

    if "*" in row:
        row = re.sub(r"\(([^\?])", r"(?:\1", row)  # Все дефолтные группы превратить в non-captured
        row = re.sub(r"\*/(\S+)/", r"(\1)", row)  # */{regex_one_word}/ -> ({regex_one_word})
        row = re.sub(r"(^|\s)\*", r"\1([^\\s]+)", row)

    # Заменяем <someting> на named-группы
    row = re.sub(r"<(\w+)>", r"(?P<\1>\\w+)", row)

    # The (?:\s|$) anchor is appended so a row matches a whole token, not a prefix
    # (interface Eth0 must not match interface Eth01). It is skipped when the row's own
    # right edge is a regexp, which defines its own boundary -- matching the pre-?/{regex}/
    # behaviour where ~/{regex}/ rows were never anchored. Two shapes:
    #   * the row ends with a ?/{regex}/ or ~/{regex}/ placeholder. The user's regexp owns
    #     the right edge, so the line may legitimately continue past the match -- e.g.
    #     interface ~/(25GE1\/0\/10(?![0-9]))/ must still match the subinterface
    #     25GE1/0/10.1501. (Anchoring here also breaks regexps that end in a zero-width
    #     assertion, like a trailing (?![0-9]) or a bare ~/(?!foo)/.)
    #   * the row ends with a hand-written zero-width lookaround that never went through
    #     the placeholder machinery, e.g. interface (?!25GE.+?/...|Vbdif(...)).
    trailing_placeholder = re.search(r"\x00\d+\x00\s*$", row) is not None

    if row.endswith("~"):
        # We determine the most specific regex for the row at matching in match_row_to_acls
        row = row[:-1] + "(.+)"
    elif row.endswith("..."):
        row = row[:-3]
    elif trailing_placeholder or _ends_with_zero_width(row):
        pass
    else:
        row += r"(?:\s|$)"
    row = re.sub(r"\s+", r"\\s+", row)
    if protected:

        def _restore(match: re.Match) -> str:
            regexp, captures = protected[int(match.group(1))]
            return f"({regexp})" if captures else f"(?:{regexp})"

        row = re.sub(r"\x00(\d+)\x00", _restore, row)
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
