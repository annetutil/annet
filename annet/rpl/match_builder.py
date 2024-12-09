from dataclasses import dataclass
from enum import Enum
from typing import Generic, Sequence, Callable, Optional, TypeVar, Any

from .condition import SingleCondition, ConditionOperator, AndCondition


class MatchField(str, Enum):
    community = "community"
    large_community = "large_community"
    extcommunity_rt = "extcommunity_rt"
    extcommunity_soo = "extcommunity_soo"
    rd = "rd"
    interface = "interface"
    protocol = "protocol"
    net_len = "net_len"
    local_pref = "local_pref"
    metric = "metric"
    family = "family"

    as_path_length = "as_path_length"
    as_path_filter = "as_path_filter"
    ipv6_prefix = "ipv6_prefix"
    ip_prefix = "ip_prefix"


ValueT = TypeVar("ValueT")
_ConditionMethod = Callable[["ConditionFactory[ValueT]", ValueT], SingleCondition[ValueT]]


def condition_method(operator: ConditionOperator) -> _ConditionMethod:
    def method(self: "ConditionFactory[ValueT]", other: ValueT) -> SingleCondition[ValueT]:
        if operator.value not in self.supported_ops:
            raise NotImplementedError(f"Operator {operator.value} is not supported for field {self.field}")
        return SingleCondition(self.field, operator, other)

    method.__name__ = operator.value
    return method


class ConditionFactory(Generic[ValueT]):
    def __init__(self, field: str, supported_ops: list[str]):
        self.field = field
        self.supported_ops = supported_ops

    # https://github.com/python/typeshed/issues/3685
    eq = __eq__ = condition_method(ConditionOperator.EQ)  # type: ignore[assignment]
    gt = __gt__ = condition_method(ConditionOperator.GT)
    ge = __ge__ = condition_method(ConditionOperator.GE)
    lt = __lt__ = condition_method(ConditionOperator.LT)
    le = __le__ = condition_method(ConditionOperator.LE)
    between_included = condition_method(ConditionOperator.BETWEEN_INCLUDED)


class SetConditionFactory(Generic[ValueT]):
    def __init__(self, field: str) -> None:
        self.field = field

    def has(self, *values: ValueT) -> SingleCondition[Sequence[ValueT]]:
        return SingleCondition(self.field, ConditionOperator.HAS, values)

    def has_any(self, *values: ValueT) -> SingleCondition[Sequence[ValueT]]:
        return SingleCondition(self.field, ConditionOperator.HAS_ANY, values)


@dataclass(frozen=True)
class PrefixMatchValue:
    names: tuple[str, ...]
    greater_equal: Optional[int]
    less_equal: Optional[int]


class Checkable:
    def __init__(self):
        self.community = SetConditionFactory[str](MatchField.community)
        self.large_community = SetConditionFactory[str](MatchField.large_community)
        self.extcommunity_rt = SetConditionFactory[str](MatchField.extcommunity_rt)
        self.extcommunity_soo = SetConditionFactory[str](MatchField.extcommunity_soo)
        self.rd = SetConditionFactory[str](MatchField.rd)
        self.interface = ConditionFactory[str](MatchField.interface, ["=="])
        self.protocol = ConditionFactory[str](MatchField.protocol, ["=="])
        self.net_len = ConditionFactory[int](MatchField.net_len, ["==", "!="])
        self.local_pref = ConditionFactory[int](MatchField.local_pref, ["<"])
        self.metric = ConditionFactory[int](MatchField.metric, ["=="])
        self.family = ConditionFactory[int](MatchField.family, ["=="])
        self.as_path_length = ConditionFactory[int](MatchField.as_path_length, ["==", ">=", "<=", "BETWEEN_INCLUDED"])

    def as_path_filter(self, name: str) -> SingleCondition[str]:
        return SingleCondition(MatchField.as_path_filter, ConditionOperator.EQ, name)

    def match_v6(
            self,
            *names: str,
            or_longer: tuple[Optional[int], Optional[int]] = (None, None),
    ) -> SingleCondition[PrefixMatchValue]:
        return SingleCondition(
            MatchField.ipv6_prefix,
            ConditionOperator.CUSTOM,
            PrefixMatchValue(names, greater_equal=or_longer[0], less_equal=or_longer[1]),
        )

    def match_v4(
            self,
            *names: str,
            or_longer: tuple[Optional[int], Optional[int]] = (None, None),
    ) -> SingleCondition[PrefixMatchValue]:
        return SingleCondition(
            MatchField.ip_prefix,
            ConditionOperator.CUSTOM,
            PrefixMatchValue(names, greater_equal=or_longer[0], less_equal=or_longer[1]),
        )


def merge_conditions(and_condition: AndCondition) -> AndCondition:
    conditions: dict[str, SingleCondition[Any]] = {}
    for condition in and_condition.conditions:
        if condition.field in conditions:
            conditions[condition.field] = conditions[condition.field].merge(condition)
        else:
            conditions[condition.field] = condition
    return AndCondition(*conditions.values())


R = Checkable()
