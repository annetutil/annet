from typing import Any, Callable, Literal, OrderedDict, Pattern, TypeAlias, TypedDict, Union


# ===RULEBOOK===


class Rulebook(TypedDict):
    patching: "PatchRulebook"
    ordering: "CompiledTree"
    deploying: OrderedDict[str, Any]
    texts: "RulebookTexts"


class RulebookTexts(TypedDict):
    patching: "PatchingText"
    ordering: str
    deploying: str


Extension: TypeAlias = Literal["rul", "order", "deploy"]


# ===PATCH_RULEBOOK===


PatchRulebook = TypedDict(
    "PatchRulebook",
    {
        "local": OrderedDict["RawRow", "PatchRule"],
        "global": OrderedDict["RawRow", "PatchRule"],
    },
)


class PatchRule(TypedDict):
    type: "Type"
    rule: str
    children: Union["PatchRulebook", None]
    attrs: "PatchRuleAttrs"


class PatchIgnoreRuleAttrs(TypedDict):
    regexp: Pattern
    diff_logic: Callable
    parent: bool
    context: dict[str, str]


class PatchNormalRuleAttrs(TypedDict):
    logic: Callable
    diff_logic: Callable
    regexp: Pattern
    reverse: str
    comment: list[str]
    multiline: bool
    parent: bool
    force_commit: bool
    ignore_case: bool
    ordered: bool
    context: dict[str, str]


PatchRuleAttrs: TypeAlias = PatchNormalRuleAttrs | PatchIgnoreRuleAttrs


PatchingText: TypeAlias = str


# Rule row without params
Row: TypeAlias = str
# Rule row with params
RawRow: TypeAlias = str
Scope: TypeAlias = Literal["local", "global"]
Type: TypeAlias = Literal["normal", "ignore"]
# Rule params validated and converted to required types
Params: TypeAlias = dict[str, Any]
# Rule params not validated and not converted to required types
RawParams: TypeAlias = dict[str, str]

ParamsScheme: TypeAlias = dict[str, dict[str, Any]]


PatchPreMerge: TypeAlias = dict[Row, "PatchPreMergeData"]


class PatchPreMergeData(TypedDict):
    rules: PatchRule
    params: RawParams
    scope: Scope


# ===ORDER_RULEBOOK===


CompiledTree: TypeAlias = list[tuple[str, "_CompiledOrderingItem"]]


class _CompiledOrderingItem(TypedDict):
    attrs: "_CompiledOrderingAttrs"
    children: "CompiledTree"


# 'global' is a keyword, so we cant use normal TypedDict declaration
_CompiledOrderingAttrs = TypedDict(
    "_CompiledOrderingAttrs",
    {
        "direct_regexp": Pattern[str],
        "reverse_regexp": Pattern[str],
        "order_reverse": bool,
        "global": bool,  # TODO: rename to something else so that it is not a keyword
        "scope": list[str] | None,
        "raw_rule": str,
        "context": Any,
        "split": bool,
    },
)
