from typing import Any, Callable, Literal, OrderedDict, Pattern, TypeAlias, TypedDict, Union


# ===RULEBOOK===


AnyRulebook: TypeAlias = Union["PatchRulebook", "OrderRulebook"]
AnyRulebookText: TypeAlias = Union["PatchingText", "OrderingText"]


class Rulebook(TypedDict):
    patching: "PatchRulebook"
    ordering: "OrderRulebook"
    deploying: OrderedDict[str, Any]
    texts: "RulebookTexts"


class RulebookTexts(TypedDict):
    patching: "PatchingText"
    ordering: "OrderingText"
    deploying: str


Extension: TypeAlias = Literal["rul", "order", "deploy"]


# ===COMMON===


# Rule row without params
Row: TypeAlias = str
# Rule row with params
RawRow: TypeAlias = str
# Rule params validated and converted to required types
Params: TypeAlias = dict[str, Any]
# Rule params not validated and not converted to required types
RawParams: TypeAlias = dict[str, str]


class ParamScheme(TypedDict):
    validator: Callable[[Any], Any]
    default: Any | Callable[[Any], Any]


ParamsScheme: TypeAlias = dict[str, ParamScheme]

# ===PATCH_RULEBOOK===


PatchRulebook = TypedDict(
    "PatchRulebook",
    {
        "local": OrderedDict["RawRow", "PatchRule"],
        "global": OrderedDict["RawRow", "PatchRule"],
    },
)


class PatchRule(TypedDict):
    type: "RuleType"
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

PatchScope: TypeAlias = Literal["local", "global"]

RuleType: TypeAlias = Literal["normal", "ignore"]

PatchPreMerge: TypeAlias = dict[Row, "PatchPreMergeData"]


class PatchPreMergeData(TypedDict):
    rules: PatchRule
    params: RawParams
    scope: PatchScope


# ===ORDER_RULEBOOK===

OrderRulebook: TypeAlias = list[tuple[RawRow, "OrderRule"]]


class OrderRule(TypedDict):
    attrs: "OrderRuleAttrs"
    children: "OrderRulebook"


# 'global' is a keyword, so we cant use normal TypedDict declaration
OrderRuleAttrs = TypedDict(
    "OrderRuleAttrs",
    {
        "direct_regexp": Pattern[str],
        "reverse_regexp": Pattern[str],
        "order_reverse": bool,
        "global": bool,  # TODO: rename to something else so that it is not a keyword
        "scope": "OrderScope",
        "raw_rule": RawRow,
        "context": dict[str, str],
        "split": bool,
    },
)

OrderingText: TypeAlias = str

OrderScope: TypeAlias = list[str] | None

OrderPreMerge: TypeAlias = list[tuple[Row, "OrderPreMergeData"]]


class OrderPreMergeData(TypedDict):
    params: RawParams
    rules: OrderRule
    raw_rule: RawRow
    insert_to_end_group: bool


Anchor: TypeAlias = Row | None

Group: TypeAlias = tuple[Anchor, "GroupData"]

GroupRows: TypeAlias = list[OrderPreMergeData]


class GroupData(TypedDict):
    anchor: OrderPreMergeData | None
    rows: GroupRows


AnchorsData: TypeAlias = dict[Row, "AnchorData"]


class AnchorData(TypedDict):
    count: int
    split: bool
