from __future__ import annotations

import functools
import re
from typing import Generator, Literal

from valkit.common import valid_bool, valid_string_list

from annet.rulebook.common import get_merged_params, validate_context_compatibility
from annet.rulebook.exceptions import RulebookSyntaxError
from annet.rulebook.types import (
    AnchorData,
    AnchorsData,
    Group,
    GroupData,
    GroupRows,
    OrderingText,
    OrderPreMerge,
    OrderPreMergeData,
    OrderRuleAttrs,
    OrderRulebook,
    RawParams,
    RawRow,
    Row,
)
from annet.vendors import registry_connector

from . import syntax


# ===RULE===
RULES: Literal["rules"] = "rules"
ATTRS: Literal["attrs"] = "attrs"
CHILDREN: Literal["children"] = "children"
TYPE: Literal["type"] = "type"
NORMAL: Literal["normal"] = "normal"

# ===PARAMS===
PARAMS: Literal["params"] = "params"
ORDER_REVERSE: Literal["order_reverse"] = "order_reverse"
GLOBAL: Literal["global"] = "global"
SCOPE: Literal["scope"] = "scope"
SPLIT: Literal["split"] = "split"
DIRECT_REGEXP: Literal["direct_regexp"] = "direct_regexp"
REVERSE_REGEXP: Literal["reverse_regexp"] = "reverse_regexp"
CONTEXT: Literal["context"] = "context"
RAW_RULE: Literal["raw_rule"] = "raw_rule"
ROW: Literal["row"] = "row"
NOT_INHERIT: Literal["not_inherit"] = "not_inherit"
INSERT_TO_END_GROUP: Literal["insert_to_end_group"] = "insert_to_end_group"

# ===GROUP===
ROWS: Literal["rows"] = "rows"
ANCHOR: Literal["anchor"] = "anchor"
COUNT: Literal["count"] = "count"


def get_params_scheme():
    return {
        ORDER_REVERSE: {
            "validator": valid_bool,
            "default": False,
        },
        GLOBAL: {
            "validator": valid_bool,
            "default": False,
        },
        SCOPE: {
            "validator": valid_string_list,
            "default": None,
        },
        SPLIT: {
            "validator": valid_bool,
            "default": False,
        },
        CONTEXT: {
            "validator": str,
            "default": None,
        },
    }


@functools.lru_cache()
def compile_ordering_text(text: str, vendor: str) -> OrderRulebook:
    return _compile_ordering(
        tree=syntax.parse_text_multi(
            text,
            params_scheme=get_params_scheme(),
        ),
        reverse_prefix=registry_connector.get()[vendor].reverse,
    )


def _compile_ordering(tree: syntax.ParsedTree, reverse_prefix: str) -> OrderRulebook:
    ordering: OrderRulebook = []
    for rule_id, attrs in tree:
        if attrs[TYPE] == NORMAL:
            ordering.append(
                (
                    rule_id,
                    {
                        ATTRS: OrderRuleAttrs(
                            {
                                DIRECT_REGEXP: syntax.compile_row_regexp(attrs[ROW]),
                                REVERSE_REGEXP: (
                                    syntax.compile_row_regexp(reverse_prefix + " " + attrs[ROW])
                                    if not attrs[ROW].startswith(reverse_prefix + " ")
                                    else syntax.compile_row_regexp(re.sub(r"^%s\s+" % (reverse_prefix), "", attrs[ROW]))
                                ),
                                ORDER_REVERSE: attrs[PARAMS][ORDER_REVERSE],
                                GLOBAL: attrs[PARAMS][GLOBAL],
                                SCOPE: attrs[PARAMS][SCOPE],
                                RAW_RULE: attrs[RAW_RULE],
                                CONTEXT: attrs[CONTEXT],
                                SPLIT: attrs[PARAMS][SPLIT],
                            }
                        ),
                        CHILDREN: _compile_ordering(attrs[CHILDREN], reverse_prefix),
                    },
                )
            )
    return ordering


def merge_order_rulebooks(parent_rulebook: OrderRulebook, child_rulebook: OrderRulebook, vendor) -> OrderRulebook:
    """Merges the parent rulebook with the child rulebook"""
    merged_rulebook: OrderRulebook = []

    parend_pre_merge = _get_pre_merge(parent_rulebook)
    child_pre_merge = _get_pre_merge(child_rulebook)
    parend_pre_merge, child_pre_merge = _apply_not_inherit_logic(parend_pre_merge, child_pre_merge)

    child_groups = _get_child_groups(parend_pre_merge, child_pre_merge)
    group_anchor, group_data = _get_next_group(child_groups)

    # Stores rules with %insert_to_end_group and anchor, rules to be added before the next anchor
    anchor_queue: GroupRows = []
    # Stores rules without %insert_to_end_group and anchor, rules to be added at the very end
    non_anchor_queue: GroupRows = []

    if group_anchor is None:
        start_group_rows, end_group_rows = _split_rows_by_insert_to_end_group_param(group_data[ROWS])
        _add_group_to_merged_rulebook(merged_rulebook, start_group_rows)
        non_anchor_queue = end_group_rows
        group_anchor, group_data = _get_next_group(child_groups)

    start_group_rows, end_group_rows = _split_rows_by_insert_to_end_group_param(group_data[ROWS])

    for row, parent_data in parend_pre_merge:
        if (group_anchor is None and _is_empty_child_group_data(group_data)) or row != group_anchor:
            merged_rulebook.append((parent_data[RAW_RULE], parent_data[RULES]))
            continue

        anchor_data = group_data[ANCHOR]

        # for mypy: anchor_data cannot be None due to prior if-condition check
        assert anchor_data is not None

        _add_group_to_merged_rulebook(merged_rulebook, anchor_queue)

        merged_row = _get_merged_row(parent_data[PARAMS], anchor_data[PARAMS], row)
        merged_attrs = _merge_attrs(
            parent_data[RULES][ATTRS], anchor_data[RULES][ATTRS], anchor_data[PARAMS], merged_row
        )
        merged_children = merge_order_rulebooks(parent_data[RULES][CHILDREN], anchor_data[RULES][CHILDREN], vendor)
        merged_rulebook.append((merged_row, {ATTRS: merged_attrs, CHILDREN: merged_children}))

        _add_group_to_merged_rulebook(merged_rulebook, start_group_rows)

        anchor_queue = end_group_rows

        group_anchor, group_data = _get_next_group(child_groups)
        start_group_rows, end_group_rows = _split_rows_by_insert_to_end_group_param(group_data[ROWS])

    _add_group_to_merged_rulebook(merged_rulebook, anchor_queue)

    _add_group_to_merged_rulebook(merged_rulebook, non_anchor_queue)

    if start_group_rows or end_group_rows or group_anchor is not None:
        anchor_data = group_data.get(ANCHOR)
        if anchor_data is not None:
            rule = anchor_data[RAW_RULE]
        else:
            rule = None
        raise RulebookSyntaxError(
            "The relative order of rules must stay the same in both parent and child rulebooks.\n"
            f"Rule in child rulebook '{rule}'.\n"
            f"Group anchor '{group_anchor}'.\n"
            f"Rules with insert_to_end_group param in group:\n\t{[row[RAW_RULE] for row in end_group_rows]}\n"
            f"Rules without insert_to_end_group param in group:\n\t{[row[RAW_RULE] for row in start_group_rows]}\n"
            "To fix this:\n"
            "\t1. Check the order of rules in the parent rulebook.\n"
            "\t2. Make sure they appear in exactly the same relative order in the child rulebook.\n"
            "\t3. Try again."
        )
    return merged_rulebook


def parse_order_rulebook_to_text(rulebook: OrderRulebook, level: int = 0) -> OrderingText:
    """Parses the rulebook into a text format"""
    lines = []
    for row, data in rulebook:
        lines.append(f"{'    ' * level}{row}")
        children_lines = parse_order_rulebook_to_text(data[CHILDREN], level + 1)
        if children_lines:
            lines.append(children_lines)
    return "\n".join(lines)


def _apply_not_inherit_logic(
    parent_pre_merge: OrderPreMerge, child_pre_merge: OrderPreMerge
) -> tuple[OrderPreMerge, OrderPreMerge]:
    """Applies the not_inherit logic to parent_pre_merge and child_pre_merge"""
    ignored_rules = set()
    applied_child_pre_merge = []
    for child_row, child_data in child_pre_merge:
        not_inherit = child_data[PARAMS].get(NOT_INHERIT)
        if not_inherit is None or not valid_bool(not_inherit if not_inherit != "" else "1"):
            applied_child_pre_merge.append((child_row, child_data))
            continue

        ignored_rules.add(child_row)
        if child_data[RULES][CHILDREN]:
            applied_child_pre_merge.append((child_row, child_data))

    applied_parent_pre_merge = []
    for parent_row, parent_data in parent_pre_merge:
        if parent_row in ignored_rules:
            continue
        applied_parent_pre_merge.append((parent_row, parent_data))
    return applied_parent_pre_merge, applied_child_pre_merge


def _split_rows_by_insert_to_end_group_param(rows: GroupRows) -> tuple[GroupRows, GroupRows]:
    """
    Splits rows into two groups based on the insert_to_end_group param

    Group 1 (without insert_to_end_group): rows to insert after the current anchor
    Group 2 (with insert_to_end_group): rows to insert before the next anchor
    """
    start_group = []
    end_group = []
    for row_data in rows:
        if row_data[INSERT_TO_END_GROUP]:
            end_group.append(row_data)
        else:
            start_group.append(row_data)
    return start_group, end_group


def _get_merged_row(parent_params: RawParams, child_params: RawParams, row: Row) -> RawRow:
    """Concatenates the rule string with the merged raw params"""
    merged_params = get_merged_params(
        parent_params,
        child_params,
    )
    return syntax.get_row_with_params(row, merged_params, get_params_scheme())


def _merge_attrs(
    parent_attrs: OrderRuleAttrs, child_attrs: OrderRuleAttrs, child_params: RawParams, raw_row: RawRow
) -> OrderRuleAttrs:
    """Merges parent_attrs and child_attrs"""
    merged_attrs = parent_attrs.copy()

    validate_context_compatibility(parent_attrs, child_attrs, raw_row)

    for param in child_params.keys():
        if param in child_attrs:
            # A dynamic key cannot be recognized by mypy as a string literal
            merged_attrs[param] = child_attrs[param]  # type: ignore[literal-required]

    merged_attrs[RAW_RULE] = raw_row

    return merged_attrs


def _get_pre_merge(rulebook: OrderRulebook) -> OrderPreMerge:
    """Created pre_merge object for merge rulebook"""
    pre_merge = []
    for raw_row, rules in rulebook:
        row, raw_params = syntax.get_row_and_raw_params(raw_row)
        insert_to_end_group = raw_params.pop(INSERT_TO_END_GROUP, "0")
        data = OrderPreMergeData(
            params=raw_params,
            rules=rules,
            raw_rule=raw_row,
            insert_to_end_group=valid_bool(insert_to_end_group if insert_to_end_group else "1"),
        )
        pre_merge.append((row, data))
    return pre_merge


def _get_next_group(child_groups: Generator[Group, None, None]) -> Group:
    """
    Retrieves the next group from child_groups
    Returns an empty group if no more groups are available
    """
    try:
        return next(child_groups)
    except StopIteration:
        # anchor, group_data
        return None, _get_empty_child_group_data()


def _get_empty_child_group_data() -> GroupData:
    """Return empty child group data"""
    return GroupData(anchor=None, rows=[])


def _get_empty_anchor_data() -> AnchorData:
    """Return empty anchor data"""
    return AnchorData(count=0, split=False)


def _is_empty_child_group_data(group_data: GroupData) -> bool:
    """Checks whether the provided group is empty"""
    return group_data[ANCHOR] is None and not group_data[ROWS]


def _get_child_groups(parent_pre_merge: OrderPreMerge, child_pre_merge: OrderPreMerge) -> Generator[Group, None, None]:
    """
    Collects rules from `child_pre_merge` into groups based on `parent_pre_merge`

    Returns:
        'anchor': the anchor the group's rules are attached to
        'group_data': group data (anchor rules, rules included in the group)
    """
    group_data = _get_empty_child_group_data()
    anchor = None
    anchors_data = _get_anchors_data(parent_pre_merge)
    for row, data in child_pre_merge:
        if row not in anchors_data:
            group_data[ROWS].append(data)
            continue

        count = anchors_data[row][COUNT]
        split = anchors_data[row][SPLIT]
        if count == 0:
            if not split:
                raise RulebookSyntaxError(
                    f"Rule '{row}' has no %split parameter but is listed multiple times in the children rulebook."
                )
            group_data[ROWS].append(data)
        else:
            anchors_data[row][COUNT] -= 1
            if not _is_empty_child_group_data(group_data):
                yield anchor, group_data
                group_data = _get_empty_child_group_data()
            anchor = row
            group_data[ANCHOR] = data

    if not _is_empty_child_group_data(group_data):
        yield anchor, group_data


def _get_anchors_data(parent_pre_merge: OrderPreMerge) -> AnchorsData:
    """
    Returns the number of anchors for each rule
    (i.e., how many times the rule appears in the parent rulebook)
    """
    anchors_data: AnchorsData = {}
    for row, data in parent_pre_merge:
        anchor_data: AnchorData = anchors_data.get(row, _get_empty_anchor_data())
        anchor_data[COUNT] = anchor_data[COUNT] + 1
        anchor_data[SPLIT] = data[RULES][ATTRS][SPLIT]
        anchors_data[row] = anchor_data
        if anchors_data[row][COUNT] > 1 and not anchors_data[row][SPLIT]:
            raise RulebookSyntaxError(
                f"Rule '{row}' has no %split parameter but is listed multiple times in the parent rulebook."
            )
    return AnchorsData(**anchors_data)


def _add_group_to_merged_rulebook(merged_rulebook: OrderRulebook, rows: GroupRows) -> None:
    """Adds rules from the group to merged_rulebook"""
    for row_data in rows:
        row, raw_params = syntax.get_row_and_raw_params(row_data[RAW_RULE])
        raw_row = syntax.get_row_with_params(row, raw_params, get_params_scheme())
        rules = row_data[RULES]
        rules[ATTRS][RAW_RULE] = raw_row
        merged_rulebook.append((raw_row, rules))
