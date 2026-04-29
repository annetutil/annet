import functools
import re
import warnings
from collections import OrderedDict as odict
from typing import Generator, Literal

from valkit.common import valid_bool, valid_string_list
from valkit.python import valid_object_path

from annet.annlib.rbparser import platform, syntax
from annet.rulebook.exceptions import RulebookSyntaxError
from annet.rulebook.types import (
    Params,
    PatchIgnoreRuleAttrs,
    PatchingText,
    PatchNormalRuleAttrs,
    PatchPreMerge,
    PatchPreMergeData,
    PatchRule,
    PatchRuleAttrs,
    PatchRulebook,
    RawParams,
    RawRow,
    Row,
    Scope,
    Type,
)
from annet.vendors import registry_connector

from .common import import_rulebook_function


# ===LOGIC_PATHS===
DEFAULT_PATCH_LOGIC = "annet.rulebook.common.default"
ORDERED_PATCH_LOGIC = "annet.rulebook.common.ordered"
REWRITE_PATCH_LOGIC = "annet.rulebook.common.rewrite"
REWRITE_DIFF_LOGIC = "annet.rulebook.common.rewrite_diff"
MULTILINE_DIFF_LOGIC = "annet.rulebook.common.multiline_diff"

# ===SCOPE===
SCOPE: Literal["scope"] = "scope"
LOCAL: Literal["local"] = "local"
GLOBAL: Literal["global"] = "global"

# ===PARAMS===
PARAMS: Literal["params"] = "params"
LOGIC: Literal["logic"] = "logic"
DIFF_LOGIC: Literal["diff_logic"] = "diff_logic"
COMMENT: Literal["comment"] = "comment"
MULTILINE: Literal["multiline"] = "multiline"
ORDERED: Literal["ordered"] = "ordered"
CONTEXT: Literal["context"] = "context"
REWRITE: Literal["rewrite"] = "rewrite"
PARENT: Literal["parent"] = "parent"
FORCE_COMMIT: Literal["force_commit"] = "force_commit"
IGNORE_CASE: Literal["ignore_case"] = "ignore_case"
ROW: Literal["row"] = "row"
NOT_INHERIT: Literal["not_inherit"] = "not_inherit"

# ===RULE===
RULES: Literal["rules"] = "rules"
RULE: Literal["rule"] = "rule"
TYPE: Literal["type"] = "type"
NORMAL: Literal["normal"] = "normal"
IGNORE: Literal["ignore"] = "ignore"
ATTRS: Literal["attrs"] = "attrs"
CHILDREN: Literal["children"] = "children"


def get_params_scheme(vendor):
    """Returning the params scheme"""
    return {
        GLOBAL: {
            "validator": valid_bool,
            "default": False,
        },
        LOGIC: {
            "validator": valid_object_path,
            "default": DEFAULT_PATCH_LOGIC,
        },
        DIFF_LOGIC: {
            "validator": valid_object_path,
            "default": registry_connector.get()[vendor].diff(False),
        },
        COMMENT: {
            "validator": valid_string_list,
            "default": [],
        },
        MULTILINE: {
            "validator": valid_bool,
            "default": False,
        },
        ORDERED: {
            "validator": valid_bool,
            "default": False,
        },
        CONTEXT: {
            "validator": str,
            "default": None,
        },
        REWRITE: {
            "validator": valid_bool,
            "default": False,
        },
        PARENT: {
            "validator": valid_bool,
            "default": False,
        },
        FORCE_COMMIT: {
            "validator": valid_bool,
            "default": False,
        },
        IGNORE_CASE: {
            "validator": valid_bool,
            "default": False,
        },
    }


@functools.lru_cache()
def compile_patching_text(text: PatchingText, vendor) -> PatchRulebook:
    return _compile_patching(
        tree=syntax.parse_text(
            text,
            params_scheme=get_params_scheme(vendor),
        ),
        reverse_prefix=registry_connector.get()[vendor].reverse,
        vendor=vendor,
    )


# =====
def _compile_patching(tree, reverse_prefix, vendor) -> PatchRulebook:
    rules = _create_empty_rulebook()
    for raw_rule, attrs in tree.items():
        regexp = _attrs_to_regexp(attrs)
        attrs = _regexp_to_attrs(regexp, attrs)
        if attrs[TYPE] == IGNORE:
            rule = PatchRule(
                type=attrs[TYPE],
                rule=attrs[ROW],
                attrs=PatchIgnoreRuleAttrs(
                    regexp=regexp,
                    diff_logic=import_rulebook_function(attrs[PARAMS][DIFF_LOGIC]),
                    parent=bool(attrs[CHILDREN]),
                    context=attrs[CONTEXT],
                ),
                children=_create_empty_rulebook(),
            )
        else:
            _validate_params_compatibility(attrs[PARAMS], raw_rule, vendor)

            if attrs[PARAMS][ORDERED]:
                attrs[PARAMS][DIFF_LOGIC] = registry_connector.get()[vendor].diff(True)
                attrs[PARAMS][LOGIC] = ORDERED_PATCH_LOGIC
            elif attrs[PARAMS][REWRITE]:
                attrs[PARAMS][DIFF_LOGIC] = REWRITE_DIFF_LOGIC
                attrs[PARAMS][LOGIC] = REWRITE_PATCH_LOGIC
            elif attrs[PARAMS][MULTILINE]:
                attrs[PARAMS][DIFF_LOGIC] = MULTILINE_DIFF_LOGIC
            rule = PatchRule(
                type=attrs[TYPE],
                rule=attrs[ROW],
                attrs=PatchNormalRuleAttrs(
                    **{
                        "logic": import_rulebook_function(attrs[PARAMS][LOGIC]),
                        "diff_logic": import_rulebook_function(attrs[PARAMS][DIFF_LOGIC]),
                        "regexp": regexp,
                        "reverse": _make_reverse(attrs[ROW], reverse_prefix, flags=regexp.flags),
                        "comment": attrs[PARAMS][COMMENT],
                        "multiline": attrs[PARAMS][MULTILINE],
                        "parent": attrs[PARAMS][PARENT] or bool(attrs[CHILDREN]),
                        "force_commit": attrs[PARAMS][FORCE_COMMIT],
                        "ignore_case": attrs[PARAMS][IGNORE_CASE],
                        "ordered": attrs[PARAMS][ORDERED],
                        "context": attrs[CONTEXT],
                    }
                ),
                children=None,
            )
            if not attrs[PARAMS][GLOBAL]:
                rule[CHILDREN] = _compile_patching(attrs[CHILDREN], reverse_prefix, vendor)
        rules[GLOBAL if attrs[PARAMS][GLOBAL] else LOCAL][raw_rule] = rule
    return rules


@functools.lru_cache()
def _make_reverse(row, reverse_prefix, flags=0):
    if row.startswith(reverse_prefix + " "):
        row = row[len(reverse_prefix + " ") :]
    else:
        row = "%s %s" % (reverse_prefix, row)

    if row[-1] == "~":
        row = row[:-1] + "{}"

    row = re.sub(r"\*(/\S+/)?", "{}", row, flags=flags)
    row = re.sub(r"\s*~(/\S+/)?", "", row, flags=flags)
    return row


def _attrs_to_regexp(attrs):
    flags = 0
    ignore_case = attrs[PARAMS][IGNORE_CASE]
    if ignore_case:
        flags |= re.IGNORECASE
    return syntax.compile_row_regexp(attrs[ROW], flags=flags)


def _regexp_to_attrs(regexp, attrs):
    attrs[PARAMS][IGNORE_CASE] = bool(regexp.flags & re.IGNORECASE)
    return attrs


def merge_patch_rulebooks(parent_rulebook: PatchRulebook, child_rulebook: PatchRulebook, vendor) -> PatchRulebook:
    """Merges the parent rulebook with the child rulebook"""
    child_pre_merge = _get_pre_merge(child_rulebook)
    parent_pre_merge = _get_pre_merge(parent_rulebook)

    merged_rulebook = _create_empty_rulebook()

    for row in uniq_local_global_rules(parent_pre_merge, child_pre_merge):
        parent_data = parent_pre_merge.get(row, None)
        child_data = child_pre_merge.get(row, None)

        if child_data is None:
            # for mypy (In this case, parend_data cannot be None)
            assert parent_data is not None
            _add_parent_to_merge_rulebook(merged_rulebook, parent_data, row, vendor)

        elif NOT_INHERIT in child_data[PARAMS] or parent_data is None:
            _add_child_to_merge_rulebook(merged_rulebook, child_data, row, vendor)

        else:
            child_rules = child_data["rules"]
            child_params = child_data["params"]
            child_scope = child_data["scope"]
            parent_rules = parent_data["rules"]
            parent_params = parent_data["params"]
            parent_scope = parent_data["scope"]

            merged_scope = get_merged_scope(parent_scope, child_scope, child_params)
            merged_row = get_merged_row(parent_params, child_params, row, vendor)
            merged_rule = get_merged_rule(parent_rules, child_rules, child_params, merged_scope, row, vendor)

            merged_rulebook[merged_scope][merged_row] = merged_rule

    return merged_rulebook


def _add_child_to_merge_rulebook(
    merged_rulebook: PatchRulebook, child_data: PatchPreMergeData, row: Row, vendor
) -> None:
    """Add child rule to merged_rulebook"""
    if NOT_INHERIT in child_data[PARAMS]:
        if GLOBAL in child_data[PARAMS]:
            raise RulebookSyntaxError(r"Usage of %not_inherit param together with %global param is not allowed.")
        elif _is_empty_rulebook(child_data[RULES][CHILDREN]):
            return None
    cutted_params = cut_default_params(child_data[PARAMS], vendor)
    row_with_params = syntax.get_row_with_params(row, cutted_params)
    merged_rulebook[child_data[SCOPE]][row_with_params] = child_data[RULES]


def _add_parent_to_merge_rulebook(
    merged_rulebook: PatchRulebook, parent_data: PatchPreMergeData, row: Row, vendor
) -> None:
    """Add parent rule to merged_rulebook"""
    cutted_params = cut_default_params(parent_data[PARAMS], vendor)
    row_with_params = syntax.get_row_with_params(row, cutted_params)
    merged_rulebook[parent_data[SCOPE]][row_with_params] = parent_data[RULES]


def _create_empty_rulebook() -> PatchRulebook:
    """Create empty patch rulebook"""
    return {LOCAL: odict(), GLOBAL: odict()}


def _is_empty_rulebook(rulebook: PatchRulebook | None) -> bool:
    """Validate patch rulebook is empty"""
    if rulebook is None:
        return True
    return not rulebook[LOCAL] and not rulebook[GLOBAL]


def _ensure_rulebook(rulebook: PatchRulebook | None = None) -> PatchRulebook:
    """
    Ensures patch rulebook has valid structure; returns empty patch rulebook if None
    """
    if rulebook is None:
        return _create_empty_rulebook()
    return rulebook


def _get_pre_merge(rulebook: PatchRulebook) -> PatchPreMerge:
    """Created pre_merge object for merge rulebook"""
    pre_merge = {}
    for scope in (LOCAL, GLOBAL):
        for raw_row, rules in rulebook[scope].items():
            row, params = syntax.get_row_and_raw_params(raw_row)
            pre_merge[row] = PatchPreMergeData(
                rules=rules,
                params=params,
                scope=scope,
            )
    return PatchPreMerge(**pre_merge)


def uniq_local_global_rules(
    parent_pre_merge: PatchPreMerge, children_pre_merge: PatchPreMerge
) -> Generator[Row, None, None]:
    """Returns each rule from parent_pre_merge and children_pre_merge exactly once"""
    seen = set()
    for pre_merge in [parent_pre_merge, children_pre_merge]:
        for row in pre_merge.keys():
            if row not in seen:
                seen.add(row)
                yield row


def get_merged_params(parent_params: RawParams, child_params: RawParams) -> RawParams:
    """Merges parent_params and child_params"""
    params = parent_params.copy()
    params.update(child_params)
    return params


def cut_default_params(params: RawParams, vendor) -> RawParams:
    """Returns a copy params without params set to default values"""
    result_param = {}
    params_scheme = get_params_scheme(vendor)
    for name, value in params.items():
        if name not in params_scheme:
            continue
        validator = params_scheme[name]["validator"]
        default = params_scheme[name]["default"]
        if validator(value if value != "" else "1") == default:
            continue
        result_param[name] = value
    return result_param


def get_merged_row(parent_params: RawParams, child_params: RawParams, row: Row, vendor) -> RawRow:
    """Concatenates the rule string with the merged raw params"""
    merged_params = get_merged_params(
        parent_params,
        child_params,
    )
    _validate_merged_params_compatibility(merged_params, row)
    cutted_params = cut_default_params(merged_params, vendor)
    return syntax.get_row_with_params(row, cutted_params)


def get_merged_scope(parent_scope: Scope, child_scope: Scope, child_params: RawParams) -> Scope:
    """Merges parent_scope and child_scope"""
    return parent_scope if child_params.get(GLOBAL) is None else child_scope


def get_merged_rule(
    parent_rules: PatchRule, child_rules: PatchRule, child_params: RawParams, scope: Scope, row: Row, vendor
) -> PatchRule:
    """Merges parent_rules and child_rules"""
    merged_type = child_rules[TYPE]
    merged_rule = child_rules[RULE]

    if scope == GLOBAL:
        merged_children = None
        if not _is_empty_rulebook(child_rules[CHILDREN]) or not _is_empty_rulebook(parent_rules[CHILDREN]):
            warnings.warn(f"Global rule '{row}' has child rules - ignoring child rules.")
    else:
        parent_children = parent_rules[CHILDREN]
        child_children = child_rules[CHILDREN]
        merged_children = merge_patch_rulebooks(
            _ensure_rulebook(parent_children), _ensure_rulebook(child_children), vendor
        )

    merged_attrs = _merge_attrs(
        parent_rules[ATTRS],
        child_rules[ATTRS],
        child_params,
        row,
        merged_type,
    )
    if (parent_rules[ATTRS][PARENT] or child_rules[ATTRS][PARENT]) and merged_type == IGNORE:
        merged_attrs[PARENT] = True
    elif not _is_empty_rulebook(merged_children) and scope == LOCAL:
        merged_attrs[PARENT] = True
    else:
        merged_attrs[PARENT] = False

    return PatchRule(
        **{
            TYPE: merged_type,
            RULE: merged_rule,
            CHILDREN: merged_children,
            ATTRS: merged_attrs,
        }
    )


def _merge_attrs(
    parent_attrs: PatchRuleAttrs, child_attrs: PatchRuleAttrs, child_params: RawParams, row: Row, rule_type: Type
) -> PatchRuleAttrs:
    """Merges parent_attrs and child_attrs"""
    merged_attrs = parent_attrs.copy()

    _validate_context_compatibility(parent_attrs, child_attrs, row)

    for param in child_params.keys():
        if param in child_attrs:
            # A dynamic key cannot be recognized by mypy as a string literal
            merged_attrs[param] = child_attrs[param]  # type: ignore[literal-required]

    if rule_type == IGNORE:
        return merged_attrs

    # After the checks above, merged_attrs, child_attrs, and parent_attrs
    # are guaranteed to be of type PatchNormalRuleAttrs
    if ORDERED in child_params:
        merged_attrs[LOGIC] = child_attrs[LOGIC]  # type: ignore[typeddict-item]
        merged_attrs[DIFF_LOGIC] = child_attrs[DIFF_LOGIC]  # type: ignore[typeddict-item]
    elif REWRITE in child_params:
        merged_attrs[LOGIC] = child_attrs[LOGIC]  # type: ignore[typeddict-item]
        merged_attrs[DIFF_LOGIC] = child_attrs[DIFF_LOGIC]  # type: ignore[typeddict-item]
    elif MULTILINE in child_params:
        merged_attrs[DIFF_LOGIC] = child_attrs[DIFF_LOGIC]  # type: ignore[typeddict-item]

    return merged_attrs


def _validate_params_compatibility(params: Params, row: str, vendor) -> None:
    """Checks compatibility of ordered/rewrite/multiline params with logic/diff_logic params at compile time"""
    used_default_logic_path = params[LOGIC] == DEFAULT_PATCH_LOGIC
    used_default_diff_logic_path = params[DIFF_LOGIC] == registry_connector.get()[vendor].diff(False)

    conflicts = [
        (ORDERED, (used_default_logic_path, used_default_diff_logic_path), (LOGIC, DIFF_LOGIC)),
        (REWRITE, (used_default_logic_path, used_default_diff_logic_path), (LOGIC, DIFF_LOGIC)),
        (MULTILINE, (used_default_diff_logic_path,), (DIFF_LOGIC,)),
    ]
    for param, checks, conflicting_params in conflicts:
        if params[param] and not all(checks):
            raise RulebookSyntaxError(
                f"Compilation error for rule '{row}'. "
                f"Param '%{param}' cannot be used together with params ({', '.join(conflicting_params)})."
            )


def _validate_merged_params_compatibility(params: RawParams, row: str) -> None:
    """Checks compatibility of ordered/rewrite/multiline params with logic/diff_logic params at merge time"""
    conflicts = [
        (ORDERED, (LOGIC, DIFF_LOGIC)),
        (REWRITE, (LOGIC, DIFF_LOGIC)),
        (MULTILINE, (DIFF_LOGIC,)),
    ]
    for param, conflicting_params in conflicts:
        if param not in params:
            continue
        elif any(conflict_param in params for conflict_param in conflicting_params):
            raise RulebookSyntaxError(
                f"Merge error for rule '{row}'. "
                f"Param '%{param}' cannot be used together with params ({', '.join(conflicting_params)})."
            )


def _validate_context_compatibility(parent_attrs: PatchRuleAttrs, child_attrs: PatchRuleAttrs, row: Row):
    """Checks compatibility of rule contexts"""
    if parent_attrs[CONTEXT] != child_attrs[CONTEXT]:
        raise RulebookSyntaxError(
            f"Merge error for rule '{row}'. Rule contexts must match in parent and child rulebooks."
        )


def parse_rulebook_to_text(rulebook: PatchRulebook, level=0) -> PatchingText:
    """Parses the rulebook into a text format"""
    lines = []
    for scope in [rulebook[LOCAL], rulebook[GLOBAL]]:
        for row, data in scope.items():
            lines.append(f"{'    ' * level}{row}")
            children = data.get(CHILDREN)
            if children is not None and not _is_empty_rulebook(children):
                children_lines = parse_rulebook_to_text(children, level + 1)
                if children_lines:
                    lines.append(children_lines)
    return "\n".join(lines)
