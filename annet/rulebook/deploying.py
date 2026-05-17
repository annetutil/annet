import functools
from collections import OrderedDict as odict
from typing import Literal

from valkit.common import valid_bool, valid_number, valid_string_list
from valkit.python import valid_object_path

from annet.annlib.lib import uniq
from annet.annlib.rbparser import syntax
from annet.annlib.rbparser.deploying import Answer, MakeMessageMatcher, compile_messages
from annet.rulebook.common import import_rulebook_function, raw_param_to_bool
from annet.rulebook.exceptions import RulebookSyntaxError
from annet.rulebook.types import (
    DeployingText,
    DeployPreMerge,
    DeployPreMergeData,
    DeployRule,
    DeployRuleAttrs,
    DeployRulebook,
    DialogPreMerge,
    Dialogs,
    ParamsScheme,
    RawParams,
    RawRow,
    Row,
)
from annet.vendors import registry_connector


# ===DEFAULTS===
DEFAULT_TIMEOUT = 30
DEFAULT_SEND_NL = True
DEFAULT_APPLY_LOGIC = "annet.rulebook.common.apply"

# ===PARAMS===
VALIDATOR: Literal["validator"] = "validator"
DEFAULT: Literal["default"] = "default"
TIMEOUT: Literal["timeout"] = "timeout"
SEND_NL: Literal["send_nl"] = "send_nl"
APPLY_LOGIC: Literal["apply_logic"] = "apply_logic"
IFCONTEXT: Literal["ifcontext"] = "ifcontext"
REGEXP: Literal["regexp"] = "regexp"
APPLY_LOGIC_NAME: Literal["apply_logic_name"] = "apply_logic_name"
NOT_INHERIT: Literal["not_inherit"] = "not_inherit"

# ===RULE===
RULES: Literal["rules"] = "rules"
ATTRS: Literal["attrs"] = "attrs"
CHILDREN: Literal["children"] = "children"
PARAMS: Literal["params"] = "params"
TYPE: Literal["type"] = "type"
NORMAL: Literal["normal"] = "normal"
ROW: Literal["row"] = "row"

# ===DIALOGS===
DIALOGS: Literal["dialogs"] = "dialogs"
DIALOG_PREFIX: Literal["dialog:"] = "dialog:"
MESSAGE: Literal["message"] = "message"
ANSWER: Literal["answer"] = "answer"


def get_params_scheme() -> ParamsScheme:
    """Returning the params scheme"""
    return {
        TIMEOUT: {
            VALIDATOR: lambda arg: valid_number(arg, min=1, type=float),
            DEFAULT: DEFAULT_TIMEOUT,
        },
        SEND_NL: {
            VALIDATOR: valid_bool,
            DEFAULT: True,
        },
        APPLY_LOGIC: {
            VALIDATOR: valid_object_path,
            DEFAULT: DEFAULT_APPLY_LOGIC,
        },
        IFCONTEXT: {
            VALIDATOR: valid_string_list,
            DEFAULT: [],
        },
    }


def get_dialog_params_scheme() -> ParamsScheme:
    """Returning the dialog params scheme"""
    return {
        SEND_NL: {
            VALIDATOR: valid_bool,
            DEFAULT: True,
        },
    }


@functools.lru_cache()
def compile_deploying_text(text: DeployingText, vendor: str) -> DeployRulebook:
    return _compile_deploying(
        tree=syntax.parse_text(
            text,
            params_scheme=get_params_scheme(),
        ),
        reverse_prefix=registry_connector.get()[vendor].reverse,
    )


# =====
def _compile_deploying(tree, reverse_prefix) -> DeployRulebook:
    deploying: DeployRulebook = odict()
    for rule_id, attrs in tree.items():
        if attrs[TYPE] == NORMAL and not attrs[ROW].startswith(DIALOG_PREFIX):
            dialogs = compile_messages(attrs[CHILDREN])
            deploying[rule_id] = {
                ATTRS: {
                    REGEXP: syntax.compile_row_regexp(attrs[ROW]),
                    TIMEOUT: attrs[PARAMS][TIMEOUT],
                    APPLY_LOGIC: import_rulebook_function(attrs[PARAMS][APPLY_LOGIC]),
                    APPLY_LOGIC_NAME: attrs[PARAMS][APPLY_LOGIC],
                    DIALOGS: dialogs,
                    IFCONTEXT: attrs[PARAMS][IFCONTEXT],
                },
                CHILDREN: _compile_deploying(attrs[CHILDREN], reverse_prefix),
            }
    return deploying


def match_deploy_rule(rules, cmd_path, context):
    for depth, row in enumerate(cmd_path):
        for rule in rules.values():
            if rule[ATTRS][REGEXP].match(row):
                ifcontext = rule[ATTRS][IFCONTEXT]
                if syntax.match_context(ifcontext, context):
                    if depth == len(cmd_path) - 1:
                        return rule
                    else:
                        rules = rule[CHILDREN]
                        if len(rules) == 0:
                            break
    # default match
    return {
        ATTRS: {
            REGEXP: syntax.compile_row_regexp("~"),
            TIMEOUT: DEFAULT_TIMEOUT,
            APPLY_LOGIC: import_rulebook_function(DEFAULT_APPLY_LOGIC),
            APPLY_LOGIC_NAME: DEFAULT_APPLY_LOGIC,
            DIALOGS: odict(),
        },
        CHILDREN: odict(),
    }


def merge_deploy_rulebooks(
    parent_rulebook: DeployRulebook,
    child_rulebook: DeployRulebook,
    vendor: str,
    parent_ifcontext: list[str] | None = None,
) -> DeployRulebook:
    """Merges the parent rulebook with the child rulebook"""
    if parent_ifcontext is None:
        parent_ifcontext = []

    merged_rulebook: DeployRulebook = odict()

    parent_pre_merge = _get_rule_pre_merge(parent_rulebook)
    child_pre_merge = _get_rule_pre_merge(child_rulebook)

    for row in uniq(parent_pre_merge, child_pre_merge):
        parent_data = parent_pre_merge.get(row)
        child_data = child_pre_merge.get(row)

        if child_data is None:
            # for mypy: In this situation, parent_data cannot be None.
            assert parent_data is not None
            add_parent_to_merge_rulebook(merged_rulebook, parent_data, row, parent_ifcontext)
            continue
        elif parent_data is None or raw_param_to_bool(child_data[PARAMS].get(NOT_INHERIT)):
            add_child_to_merge_rulebook(merged_rulebook, child_data, row, parent_ifcontext)
            continue
        parent_params = parent_data[PARAMS]
        parent_rules = parent_data[RULES]
        child_params = child_data[PARAMS]
        child_rules = child_data[RULES]
        merged_row = get_merged_row(row, parent_params, child_params)
        merged_rule = get_merged_rule(parent_rules, child_rules, child_params, vendor, merged_row, parent_ifcontext)
        merged_rulebook[merged_row] = merged_rule
    return merged_rulebook


def dump_deploy_rulebook(rulebook: DeployRulebook, level: int = 0) -> DeployingText:
    """Dumps the rulebook into a text format"""
    lines = []
    for row, rules in rulebook.items():
        lines.append(f"{'    ' * level}{row}")
        children = rules[CHILDREN]
        dialogs = rules[ATTRS][DIALOGS]
        if dialogs:
            lines.append(dump_dialogs(dialogs, level + 1))
        if children:
            lines.append(dump_deploy_rulebook(children, level + 1))
    return "\n".join(lines)


def dump_dialogs(dialogs: Dialogs, level: int) -> str:
    """Dumps the dialogs into a text format"""
    lines = []
    for message, answer in dialogs.items():
        answer_with_params = syntax.get_row_with_params(answer.text, message.raw_params, get_dialog_params_scheme())
        lines.append(f"{'    ' * level}{DIALOG_PREFIX} {message.text} ::: {answer_with_params}")
    return "\n".join(lines)


def get_merged_row(row: Row, parent_params: RawParams, child_params: RawParams) -> RawRow:
    """Concatenates the rule string with the merged raw params"""
    merged_params = parent_params.copy()
    merged_params.update(child_params)
    merged_row = syntax.get_row_with_params(row, merged_params, get_params_scheme())
    return merged_row


def get_merged_rule(
    parent_rules: DeployRule,
    child_rules: DeployRule,
    child_params: RawParams,
    vendor: str,
    row: RawRow,
    parent_ifcontext: list[str],
) -> DeployRule:
    """Merges parent_rules and child_rules"""
    parent_attrs = parent_rules[ATTRS]
    parent_children = parent_rules[CHILDREN]
    child_attrs = child_rules[ATTRS]
    child_children = child_rules[CHILDREN]

    merged_attrs = get_merged_attrs(parent_attrs, child_attrs, child_params)
    curr_ifcontext = merged_attrs[IFCONTEXT]
    if curr_ifcontext and parent_ifcontext:
        check_ifcontext_compatibility(curr_ifcontext, parent_ifcontext, row)
    merged_children = merge_deploy_rulebooks(
        parent_children, child_children, vendor, get_effective_ifcontext(curr_ifcontext, parent_ifcontext)
    )
    return {ATTRS: merged_attrs, CHILDREN: merged_children}


def get_merged_attrs(
    parent_attrs: DeployRuleAttrs, child_attrs: DeployRuleAttrs, child_params: RawParams
) -> DeployRuleAttrs:
    """Merges parent_attrs and child_attrs"""
    merged_attrs = parent_attrs.copy()

    for param in child_params.keys():
        if param in child_attrs:
            # A dynamic key cannot be recognized by mypy as a string literal
            merged_attrs[param] = child_attrs[param]  # type: ignore[literal-required]

    if APPLY_LOGIC in child_params:
        merged_attrs[APPLY_LOGIC_NAME] = child_attrs[APPLY_LOGIC_NAME]

    merged_attrs[DIALOGS] = merge_dialogs(parent_attrs[DIALOGS], child_attrs[DIALOGS])

    return merged_attrs


def merge_dialogs(parent_dialogs: Dialogs, child_dialogs: Dialogs) -> Dialogs:
    """Merges parent_dialogs and child_dialogs"""
    merged_dialogs = odict()
    parent_pre_merge = get_dialog_pre_merge(parent_dialogs)
    child_pre_merge = get_dialog_pre_merge(child_dialogs)
    for message in uniq(parent_pre_merge, child_pre_merge):
        parent_data = parent_pre_merge.get(message)
        child_data = child_pre_merge.get(message)

        if child_data is None:
            # for mypy: In this situation, parent_data cannot be None.
            assert parent_data is not None
            merged_dialogs[parent_data[MESSAGE]] = parent_data[ANSWER]
            continue
        elif raw_param_to_bool(child_data[MESSAGE].raw_params.get(NOT_INHERIT)):
            continue
        elif parent_data is None:
            merged_dialogs[child_data[MESSAGE]] = child_data[ANSWER]
            continue
        merged_message, merged_answer = get_merged_dialog(
            parent_data[MESSAGE],
            parent_data[ANSWER],
            child_data[MESSAGE],
            child_data[ANSWER],
        )
        merged_dialogs[merged_message] = merged_answer
    return merged_dialogs


def get_merged_dialog(
    parent_message: MakeMessageMatcher, parent_answer: Answer, child_message: MakeMessageMatcher, child_answer: Answer
) -> tuple[MakeMessageMatcher, Answer]:
    """Merges parent dialog (message, answer) and child dialog (message, answer)"""
    merged_params = parent_message.raw_params.copy()
    merged_params.update(child_message.raw_params)

    merged_message = MakeMessageMatcher(parent_message.text)
    merged_message.raw_params = merged_params

    if SEND_NL in child_message.raw_params:
        send_nl = child_answer.send_nl
    else:
        send_nl = parent_answer.send_nl
    merged_answer = Answer(
        text=child_answer.text,
        send_nl=send_nl,
    )

    return merged_message, merged_answer


def get_dialog_pre_merge(dialogs: Dialogs) -> DialogPreMerge:
    """Created pre_merge object for merge dialogs"""
    pre_merge: DialogPreMerge = odict()
    for message, answer in dialogs.items():
        pre_merge[message] = {
            MESSAGE: message,
            ANSWER: answer,
        }
    return pre_merge


def add_parent_to_merge_rulebook(
    merged_rulebook: DeployRulebook, parent_data: DeployPreMergeData, row: Row, parent_ifcontext: list[str]
) -> None:
    """Add parent rule to merged_rulebook"""
    raw_row = syntax.get_row_with_params(row, parent_data[PARAMS], get_params_scheme())
    check_rulebook_ifcontext_compatibility(odict({raw_row: parent_data[RULES]}), parent_ifcontext)
    merged_rulebook[raw_row] = parent_data[RULES]


def add_child_to_merge_rulebook(
    merged_rulebook: DeployRulebook, child_data: DeployPreMergeData, row: Row, parent_ifcontext: list[str]
) -> None:
    """Add child rule to merged_rulebook"""
    not_inherit = raw_param_to_bool(child_data[PARAMS].get(NOT_INHERIT))
    children = child_data[RULES][CHILDREN]
    dialogs = child_data[RULES][ATTRS][DIALOGS]
    if not_inherit and not children and not dialogs:
        return None

    if children:
        child_data[RULES][CHILDREN] = _apply_not_inherit_to_child_rules(children)

    if dialogs:
        child_data[RULES][ATTRS][DIALOGS] = _apply_not_inherit_to_dialogs(dialogs)

    row_with_params = syntax.get_row_with_params(row, child_data[PARAMS], get_params_scheme())
    check_rulebook_ifcontext_compatibility(odict({row_with_params: child_data[RULES]}), parent_ifcontext)
    merged_rulebook[row_with_params] = child_data[RULES]


def _apply_not_inherit_to_child_rules(rulebook: DeployRulebook) -> DeployRulebook:
    """Applies the logic of the %not_inherit param to all rules in the child_rulebook"""
    applied_rulebook = odict()
    for raw_row, rules in rulebook.items():
        row, raw_params = syntax.get_row_and_raw_params(raw_row)
        not_inherit = raw_param_to_bool(raw_params.get(NOT_INHERIT))
        if not_inherit and not rules[CHILDREN] and not rules[ATTRS][DIALOGS]:
            continue
        if rules[CHILDREN]:
            rules[CHILDREN] = _apply_not_inherit_to_child_rules(rules[CHILDREN])
        if rules[ATTRS][DIALOGS]:
            rules[ATTRS][DIALOGS] = _apply_not_inherit_to_dialogs(rules[ATTRS][DIALOGS])
        raw_row = syntax.get_row_with_params(row, raw_params, get_params_scheme())

        applied_rulebook[raw_row] = rules

    return applied_rulebook


def _apply_not_inherit_to_dialogs(dialogs: Dialogs) -> Dialogs:
    """Applies the logic of the %not_inherit param to all dialogs"""
    applied_dialogs = odict()
    for message, answer in dialogs.items():
        if raw_param_to_bool(message.raw_params.get(NOT_INHERIT)):
            continue
        applied_dialogs[message] = answer
    return applied_dialogs


def check_rulebook_ifcontext_compatibility(rulebook: DeployRulebook, parent_ifcontext: list[str]) -> None:
    """Checks compatibility of rulebook ifcontext"""
    for row, rules in rulebook.items():
        curr_ifcontext = rules[ATTRS][IFCONTEXT]
        if curr_ifcontext and parent_ifcontext:
            check_ifcontext_compatibility(curr_ifcontext, parent_ifcontext, row)
        check_rulebook_ifcontext_compatibility(
            rules[CHILDREN], get_effective_ifcontext(curr_ifcontext, parent_ifcontext)
        )


def get_effective_ifcontext(curr_ifcontext: list[str], parent_ifcontext: list[str]) -> list[str]:
    """Returns current ifcontext if curr_ifcontext is not empty, otherwise returns parent_ifcontext"""
    return curr_ifcontext or parent_ifcontext


def check_ifcontext_compatibility(curr_ifcontext: list[str], parent_ifcontext: list[str], row: RawRow) -> None:
    """Checks compatibility of rule ifcontext"""
    if set(curr_ifcontext) - set(parent_ifcontext):
        raise RulebookSyntaxError(
            f"The rule {row} specifies a %ifcontext not present in the parent rules. "
            f"Current rule %ifcontext: {curr_ifcontext}, parent rules %ifcontext: {parent_ifcontext}."
        )


def _get_rule_pre_merge(rulebook: DeployRulebook) -> DeployPreMerge:
    """Created pre_merge object for merge rulebooks"""
    pre_merge: DeployPreMerge = odict()
    for raw_row, rules in rulebook.items():
        row, raw_params = syntax.get_row_and_raw_params(raw_row)
        raw_params.pop(IFCONTEXT, None)
        raw_ifcontext_value = ",".join(rules[ATTRS][IFCONTEXT])
        if raw_ifcontext_value:
            row = f"{row} %{IFCONTEXT}={raw_ifcontext_value}"
        pre_merge[row] = {
            RULES: rules,
            PARAMS: raw_params,
        }
    return pre_merge
