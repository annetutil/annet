import functools
import re
import warnings
from collections import OrderedDict as odict
from typing import Any, Generator, cast

from valkit.common import valid_bool, valid_string_list
from valkit.python import valid_object_path

from annet.annlib.rbparser import platform, syntax
from annet.annlib.rbparser.exceptions import RulebookSyntaxError
from annet.rulebook.common import (
    get_merged_params,
    import_rulebook_function,
    raw_param_to_bool,
    validate_context_compatibility,
)
from annet.rulebook.types import (
    Params,
    ParamsScheme,
    PatchIgnoreRuleAttrs,
    PatchingText,
    PatchNormalRuleAttrs,
    PatchPreMerge,
    PatchPreMergeData,
    PatchRule,
    PatchRuleAttrs,
    PatchRulebook,
    PatchScope,
    RawParams,
    RawRow,
    Row,
    RuleType,
)
from annet.vendors import registry_connector


# ===LOGIC_PATHS===
DEFAULT_PATCH_LOGIC = "annet.rulebook.common.default"
ORDERED_PATCH_LOGIC = "annet.rulebook.common.ordered"
REWRITE_PATCH_LOGIC = "annet.rulebook.common.rewrite"
REWRITE_DIFF_LOGIC = "annet.rulebook.common.rewrite_diff"
MULTILINE_DIFF_LOGIC = "annet.rulebook.common.multiline_diff"


def get_params_scheme(vendor: str) -> ParamsScheme:
    """Returning the params scheme"""
    return {
        "global": {
            "validator": valid_bool,
            "default": False,
        },
        "logic": {
            "validator": valid_object_path,
            "default": DEFAULT_PATCH_LOGIC,
        },
        "diff_logic": {
            "validator": valid_object_path,
            "default": registry_connector.get()[vendor].diff(False),
        },
        "comment": {
            "validator": valid_string_list,
            "default": [],
        },
        "multiline": {
            "validator": valid_bool,
            "default": False,
        },
        "ordered": {
            "validator": valid_bool,
            "default": False,
        },
        "context": {
            "validator": str,
            "default": None,
        },
        "rewrite": {
            "validator": valid_bool,
            "default": False,
        },
        "parent": {
            "validator": valid_bool,
            "default": False,
        },
        "force_commit": {
            "validator": valid_bool,
            "default": False,
        },
        "ignore_case": {
            "validator": valid_bool,
            "default": False,
        },
    }


@functools.lru_cache()
def compile_patching_text(text: PatchingText, vendor: str) -> PatchRulebook:
    return _compile_patching(
        tree=syntax.parse_text(
            text,
            params_scheme=get_params_scheme(vendor),
        ),
        reverse_prefix=registry_connector.get()[vendor].reverse,
        vendor=vendor,
    )


# =====
def _compile_patching(tree: dict[str, Any], reverse_prefix: str, vendor: str) -> PatchRulebook:
    rules = _create_empty_rulebook()
    for raw_rule, attrs in tree.items():
        regexp = _attrs_to_regexp(attrs)
        attrs = _regexp_to_attrs(regexp, attrs)
        if attrs["type"] == "ignore":
            rule = PatchRule(
                type=attrs["type"],
                rule=attrs["row"],
                attrs=PatchIgnoreRuleAttrs(
                    regexp=regexp,
                    diff_logic=import_rulebook_function(attrs["params"]["diff_logic"]),
                    parent=bool(attrs["children"]),
                    context=attrs["context"],
                ),
                children=_create_empty_rulebook(),
            )
        else:
            _validate_params_compatibility(attrs["params"], raw_rule, vendor)

            if attrs["params"]["ordered"]:
                attrs["params"]["diff_logic"] = registry_connector.get()[vendor].diff(True)
                attrs["params"]["logic"] = ORDERED_PATCH_LOGIC
            elif attrs["params"]["rewrite"]:
                attrs["params"]["diff_logic"] = REWRITE_DIFF_LOGIC
                attrs["params"]["logic"] = REWRITE_PATCH_LOGIC
            elif attrs["params"]["multiline"]:
                attrs["params"]["diff_logic"] = MULTILINE_DIFF_LOGIC
            rule = PatchRule(
                type=attrs["type"],
                rule=attrs["row"],
                attrs=PatchNormalRuleAttrs(
                    **{
                        "logic": import_rulebook_function(attrs["params"]["logic"]),
                        "diff_logic": import_rulebook_function(attrs["params"]["diff_logic"]),
                        "regexp": regexp,
                        "reverse": _make_reverse(attrs["row"], reverse_prefix, flags=regexp.flags),
                        "comment": attrs["params"]["comment"],
                        "multiline": attrs["params"]["multiline"],
                        "parent": attrs["params"]["parent"] or bool(attrs["children"]),
                        "force_commit": attrs["params"]["force_commit"],
                        "ignore_case": attrs["params"]["ignore_case"],
                        "ordered": attrs["params"]["ordered"],
                        "context": attrs["context"],
                    }
                ),
                children=None,
            )
            if not attrs["params"]["global"]:
                rule["children"] = _compile_patching(attrs["children"], reverse_prefix, vendor)
        rules["global" if attrs["params"]["global"] else "local"][raw_rule] = rule
    return rules


@functools.lru_cache()
def _make_reverse(row: str, reverse_prefix: str, flags: int = 0) -> str:
    if row.startswith(reverse_prefix + " "):
        row = row[len(reverse_prefix + " ") :]
    else:
        row = "%s %s" % (reverse_prefix, row)

    if row[-1] == "~":
        row = row[:-1] + "{}"

    # Handle the arbitrary-regexp placeholders before the * substitution below, so any
    # *, (...) inside the user's own regexp is not mistaken for a capturing placeholder.
    # Mirroring compile_row_regexp: ~/{regex}/ captures, so it becomes a {}; ?/{regex}/
    # captures nothing, so it is dropped entirely (no {}). The first / after ?/ or ~/
    # closes the placeholder, so the regexp cannot itself contain a literal / (hence
    # [^/]+). Surrounding whitespace of the dropped ?/.../ collapses to keep words
    # separated whether the placeholder is leading, trailing, or in the middle.
    row = re.sub(r"~/[^/]+/", "{}", row, flags=flags)
    row = re.sub(r"\s*\?/[^/]+/\s*", " ", row, flags=flags)

    row = re.sub(r"\*(/\S+/)?", "{}", row, flags=flags)
    return row.strip()


def _attrs_to_regexp(attrs: dict[str, Any]) -> re.Pattern[str]:
    flags = 0
    ignore_case = attrs["params"]["ignore_case"]
    if ignore_case:
        flags |= re.IGNORECASE
    return syntax.compile_row_regexp(attrs["row"], flags=flags)


def _regexp_to_attrs(regexp: re.Pattern[str], attrs: dict[str, Any]) -> dict[str, Any]:
    attrs["params"]["ignore_case"] = bool(regexp.flags & re.IGNORECASE)
    return attrs


def merge_patch_rulebooks(parent_rulebook: PatchRulebook, child_rulebook: PatchRulebook, vendor: str) -> PatchRulebook:
    """Merges the parent rulebook with the child rulebook"""
    child_pre_merge = _get_pre_merge(child_rulebook)
    parent_pre_merge = _get_pre_merge(parent_rulebook)

    merged_rulebook = _create_empty_rulebook()

    for row in _uniq_local_global_rules(parent_pre_merge, child_pre_merge):
        parent_data = parent_pre_merge.get(row, None)
        child_data = child_pre_merge.get(row, None)

        if child_data is None:
            # for mypy (In this case, parent_data cannot be None)
            assert parent_data is not None
            _add_parent_to_merge_rulebook(merged_rulebook, parent_data, row, vendor)
        elif raw_param_to_bool(child_data["params"].get("not_inherit")) or parent_data is None:
            _add_child_to_merge_rulebook(merged_rulebook, child_data, row, vendor)

        else:
            child_rules = child_data["rules"]
            child_params = child_data["params"]
            child_scope = child_data["scope"]
            parent_rules = parent_data["rules"]
            parent_params = parent_data["params"]
            parent_scope = parent_data["scope"]

            merged_scope = _get_merged_scope(parent_scope, child_scope, child_params)
            merged_row = _get_merged_row(parent_params, child_params, row, vendor)
            merged_rule = _get_merged_rule(parent_rules, child_rules, child_params, merged_scope, row, vendor)

            merged_rulebook[merged_scope][merged_row] = merged_rule

    return merged_rulebook


def dump_patch_rulebook(rulebook: PatchRulebook, level: int = 0) -> PatchingText:
    """Parses the rulebook into a text format"""
    lines = []
    for scope in [rulebook["local"], rulebook["global"]]:
        for row, data in scope.items():
            lines.append(f"{'    ' * level}{row}")
            children = data.get("children")
            if children is not None and not _is_empty_rulebook(children):
                children_lines = dump_patch_rulebook(children, level + 1)
                if children_lines:
                    lines.append(children_lines)
    return "\n".join(lines)


def _add_child_to_merge_rulebook(
    merged_rulebook: PatchRulebook, child_data: PatchPreMergeData, row: Row, vendor: str
) -> None:
    """Add child rule to merged_rulebook"""
    if raw_param_to_bool(child_data["params"].get("not_inherit")):
        if "global" in child_data["params"]:
            raise RulebookSyntaxError(r"Usage of %not_inherit param together with %global param is not allowed.")
        elif _is_empty_rulebook(child_data["rules"]["children"]):
            return None

    if not _is_empty_rulebook(child_data["rules"]["children"]):
        child_data["rules"]["children"] = _apply_not_inherit_to_child_rules(
            cast(PatchRulebook, child_data["rules"]["children"]),
            vendor,
        )

    row_with_params = syntax.get_row_with_params(row, child_data["params"], get_params_scheme(vendor))

    if child_data["rules"]["type"] != "ignore":
        child_data["rules"]["attrs"]["parent"] = not _is_empty_rulebook(child_data["rules"]["children"])

    merged_rulebook[child_data["scope"]][row_with_params] = child_data["rules"]


def _apply_not_inherit_to_child_rules(child_rulebook: PatchRulebook, vendor: str) -> PatchRulebook:
    """Applies the logic of the %not_inherit param to all rules in the child_rulebook"""
    applied_rulebook = _create_empty_rulebook()
    for scope in ("local", "global"):
        for raw_row, rules in child_rulebook[scope].items():
            row, raw_params = syntax.get_row_and_raw_params(raw_row)

            if raw_param_to_bool(raw_params.get("not_inherit")):
                if "global" in raw_params:
                    raise RulebookSyntaxError(
                        r"Usage of %not_inherit param together with %global param is not allowed."
                    )
                if _is_empty_rulebook(rules["children"]):
                    continue
                del raw_params["not_inherit"]

            raw_row = syntax.get_row_with_params(row, raw_params, get_params_scheme(vendor))

            # "rule" holds the bare command, the way _compile_patching fills it from
            # attrs["row"]: without params, and without the leading "!" of an ignore rule.
            rules["rule"] = row[1:].strip() if rules["type"] == "ignore" else row

            if not _is_empty_rulebook(rules["children"]):
                rules["children"] = _apply_not_inherit_to_child_rules(
                    cast(PatchRulebook, rules["children"]),
                    vendor,
                )

            if rules["type"] != "ignore":
                rules["attrs"]["parent"] = not _is_empty_rulebook(rules["children"])

            applied_rulebook[scope][raw_row] = rules

    return applied_rulebook


def _add_parent_to_merge_rulebook(
    merged_rulebook: PatchRulebook, parent_data: PatchPreMergeData, row: Row, vendor: str
) -> None:
    """Add parent rule to merged_rulebook"""
    row_with_params = syntax.get_row_with_params(row, parent_data["params"], get_params_scheme(vendor))
    merged_rulebook[parent_data["scope"]][row_with_params] = parent_data["rules"]


def _create_empty_rulebook() -> PatchRulebook:
    """Create empty patch rulebook"""
    return {"local": odict(), "global": odict()}


def _is_empty_rulebook(rulebook: PatchRulebook | None) -> bool:
    """Validate patch rulebook is empty"""
    if rulebook is None:
        return True
    return not rulebook["local"] and not rulebook["global"]


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
    for scope in ("local", "global"):
        for raw_row, rules in rulebook[scope].items():
            row, params = syntax.get_row_and_raw_params(raw_row)
            pre_merge[row] = PatchPreMergeData(
                rules=rules,
                params=params,
                scope=scope,
            )
    return PatchPreMerge(**pre_merge)


def _uniq_local_global_rules(
    parent_pre_merge: PatchPreMerge, children_pre_merge: PatchPreMerge
) -> Generator[Row, None, None]:
    """Returns each rule from parent_pre_merge and children_pre_merge exactly once"""
    seen = set()
    for pre_merge in [parent_pre_merge, children_pre_merge]:
        for row in pre_merge.keys():
            if row not in seen:
                seen.add(row)
                yield row


def _get_merged_row(parent_params: RawParams, child_params: RawParams, row: Row, vendor: str) -> RawRow:
    """Concatenates the rule string with the merged raw params"""
    merged_params = get_merged_params(
        parent_params,
        child_params,
    )
    _validate_merged_params_compatibility(merged_params, row)
    return syntax.get_row_with_params(row, merged_params, get_params_scheme(vendor))


def _get_merged_scope(parent_scope: PatchScope, child_scope: PatchScope, child_params: RawParams) -> PatchScope:
    """Merges parent_scope and child_scope"""
    return parent_scope if child_params.get("global") is None else child_scope


def _get_merged_rule(
    parent_rules: PatchRule, child_rules: PatchRule, child_params: RawParams, scope: PatchScope, row: Row, vendor: str
) -> PatchRule:
    """Merges parent_rules and child_rules"""
    merged_type = child_rules["type"]
    merged_rule = child_rules["rule"]

    if scope == "global":
        merged_children = None
        if not _is_empty_rulebook(child_rules["children"]) or not _is_empty_rulebook(parent_rules["children"]):
            warnings.warn(f"Global rule '{row}' has child rules - ignoring child rules.")
    else:
        parent_children = parent_rules["children"]
        child_children = child_rules["children"]
        merged_children = merge_patch_rulebooks(
            _ensure_rulebook(parent_children), _ensure_rulebook(child_children), vendor
        )

    merged_attrs = _merge_attrs(
        parent_rules["attrs"],
        child_rules["attrs"],
        child_params,
        row,
        merged_type,
    )
    if (parent_rules["attrs"]["parent"] or child_rules["attrs"]["parent"]) and merged_type == "ignore":
        merged_attrs["parent"] = True
    elif not _is_empty_rulebook(merged_children) and scope == "local":
        merged_attrs["parent"] = True
    else:
        merged_attrs["parent"] = False

    return PatchRule(
        **{
            "type": merged_type,
            "rule": merged_rule,
            "children": merged_children,
            "attrs": merged_attrs,
        }
    )


def _merge_attrs(
    parent_attrs: PatchRuleAttrs, child_attrs: PatchRuleAttrs, child_params: RawParams, row: Row, rule_type: RuleType
) -> PatchRuleAttrs:
    """Merges parent_attrs and child_attrs"""
    merged_attrs = parent_attrs.copy()

    validate_context_compatibility(parent_attrs, child_attrs, row)

    for param in child_params.keys():
        if param in child_attrs:
            # A dynamic key cannot be recognized by mypy as a string literal
            merged_attrs[param] = child_attrs[param]  # type: ignore[literal-required]

    if rule_type == "ignore":
        return merged_attrs

    # After the checks above, merged_attrs, child_attrs, and parent_attrs
    # are guaranteed to be of type PatchNormalRuleAttrs
    if "ordered" in child_params:
        merged_attrs["logic"] = child_attrs["logic"]  # type: ignore[typeddict-item]
        merged_attrs["diff_logic"] = child_attrs["diff_logic"]
    elif "rewrite" in child_params:
        merged_attrs["logic"] = child_attrs["logic"]  # type: ignore[typeddict-item]
        merged_attrs["diff_logic"] = child_attrs["diff_logic"]
    elif "multiline" in child_params:
        merged_attrs["diff_logic"] = child_attrs["diff_logic"]

    return merged_attrs


def _validate_params_compatibility(params: Params, row: str, vendor: str) -> None:
    """Checks compatibility of ordered/rewrite/multiline params with logic/diff_logic params at compile time"""
    used_default_logic_path = params["logic"] == DEFAULT_PATCH_LOGIC
    used_default_diff_logic_path = params["diff_logic"] == registry_connector.get()[vendor].diff(False)

    conflicts = [
        ("ordered", (used_default_logic_path, used_default_diff_logic_path), ("logic", "diff_logic")),
        ("rewrite", (used_default_logic_path, used_default_diff_logic_path), ("logic", "diff_logic")),
        ("multiline", (used_default_diff_logic_path,), ("diff_logic",)),
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
        ("ordered", ("logic", "diff_logic")),
        ("rewrite", ("logic", "diff_logic")),
        ("multiline", ("diff_logic",)),
    ]
    for param, conflicting_params in conflicts:
        if param not in params:
            continue
        elif any(conflict_param in params for conflict_param in conflicting_params):
            raise RulebookSyntaxError(
                f"Merge error for rule '{row}'. "
                f"Param '%{param}' cannot be used together with params ({', '.join(conflicting_params)})."
            )
