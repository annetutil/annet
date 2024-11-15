from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar, Sequence, Union, Callable, Any


class ConditionOperator(Enum):
    EQ = "=="
    GE = ">="
    GT = ">"
    LE = "<="
    LT = "<"

    HAS = "has"
    HAS_ANY = "has_any"

    CUSTOM = "custom"


ValueT = TypeVar("ValueT")


@dataclass(frozen=True)
class SingleCondition(Generic[ValueT]):
    field: str
    operator: ConditionOperator
    value: ValueT

    def __and__(self, other: "Condition") -> "AndCondition":
        return AndCondition(self, other)


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


class Checkable:
    def __init__(self):
        self.community = SetConditionFactory[str]("community")
        self.extcommunity = SetConditionFactory[str]("extcommunity")
        self.rd = SetConditionFactory[str]("rd")
        self.interface = ConditionFactory[str]("interface", ["=="])
        self.protocol = ConditionFactory[str]("protocol", ["=="])
        self.as_path_length = ConditionFactory[int]("as_path_length", ["==", ">="])


R = Checkable()
Condition = Union[SingleCondition, "AndCondition"]


class AndCondition:
    def __init__(self, *conditions: Condition):
        self.conditions: list[SingleCondition[Any]] = []
        for c in conditions:
            self.conditions.extend(self._unpack(c))
        self._check_duplicates()

    def _check_duplicates(self) -> None:
        seen_fields: set[str] = set()
        for condition in self.conditions:
            if condition.field in seen_fields:
                raise ValueError(f"Cannot have multiple condition on field {condition.field}")

    def _unpack(self, other: Condition) -> Sequence[SingleCondition]:
        if isinstance(other, AndCondition):
            return other.conditions
        return [other]

    def __and__(self, other: Condition) -> "AndCondition":
        return AndCondition(*self.conditions, other)

    def __iadd__(self, other):
        self.conditions.extend(self._unpack(other))

    def __repr__(self):
        conditions = ", ".join(repr(c) for c in self.conditions)
        return f"AndCondition({conditions})"

    def __getitem__(self, item: str) -> SingleCondition[Any]:
        return next(c for c in self.conditions if c.field == item)

    def __contains__(self, item: str) -> bool:
        return any(c.field == item for c in self.conditions)

    def __len__(self) -> int:
        return len(self.conditions)

    def __iter__(self) -> Iterator[SingleCondition[Any]]:
        return iter(self.conditions)
