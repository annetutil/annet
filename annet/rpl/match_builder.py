from dataclasses import dataclass
from enum import Enum
from typing import Generic, Sequence, Callable, Optional, TypeVar

from .condition import SingleCondition, ConditionOperator


class MatchField(str, Enum):
    community = "community"
    extcommunity = "extcommunity"
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

    __eq__ = condition_method(ConditionOperator.EQ)
    __gt__ = condition_method(ConditionOperator.GT)
    __ge__ = condition_method(ConditionOperator.GE)
    __lt__ = condition_method(ConditionOperator.LT)
    __le__ = condition_method(ConditionOperator.LE)


class SetConditionFactory(Generic[ValueT]):
    def __init__(self, field: str):
        self.field = field

    def has(self, *values: str) -> SingleCondition[list[ValueT]]:
        return SingleCondition(self.field, ConditionOperator.HAS, values)

    def has_any(self, *values: str) -> SingleCondition[list[ValueT]]:
        return SingleCondition(self.field, ConditionOperator.HAS_ANY, values)


@dataclass(frozen=True)
class PrefixMatchValue:
    names: Sequence[str]
    or_longer: Optional[tuple[int, int]]  # ????


class Checkable:
    def __init__(self):
        self.community = SetConditionFactory[str](MatchField.community)
        self.extcommunity = SetConditionFactory[str](MatchField.extcommunity)
        self.rd = SetConditionFactory[str](MatchField.rd)
        self.interface = ConditionFactory[str](MatchField.interface, ["=="])
        self.protocol = ConditionFactory[str](MatchField.protocol, ["=="])
        self.net_len = ConditionFactory[int](MatchField.net_len, ["==", "!="])
        self.local_pref = ConditionFactory[int](MatchField.local_pref, ["<"])
        self.metric = ConditionFactory[int](MatchField.metric, ["=="])
        self.family = ConditionFactory[int](MatchField.family, ["=="])
        self.as_path_length = ConditionFactory[int](MatchField.as_path_length, ["==", ">="])

    def as_path_filter(self, name: str) -> SingleCondition[str]:
        return SingleCondition(MatchField.as_path_filter, ConditionOperator.EQ, name)

    def match_v6(self, *names: str, or_longer: Optional[tuple[int, int]] = None) -> SingleCondition[PrefixMatchValue]:
        return SingleCondition(MatchField.ipv6_prefix, ConditionOperator.CUSTOM, PrefixMatchValue(names, or_longer))

    def match_v4(self, *names: str, or_longer: Optional[tuple[int, int]] = None) -> SingleCondition[PrefixMatchValue]:
        return SingleCondition(MatchField.ip_prefix, ConditionOperator.CUSTOM, PrefixMatchValue(names, or_longer))


R = Checkable()
