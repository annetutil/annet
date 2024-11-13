from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar, Sequence, Union, Callable, Any


class Operator(Enum):
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
class BaseCondition(Generic[ValueT]):
    field: str
    operator: Operator
    value: ValueT

    def __and__(self, other: "Condition") -> "AndCondition":
        return AndCondition(self, other)


_ConditionMethod = Callable[["ConditionFactory[ValueT]", ValueT], BaseCondition[ValueT]]


def condition_method(operator: Operator) -> _ConditionMethod:
    def method(self: "ConditionFactory[ValueT]", other: ValueT) -> BaseCondition[ValueT]:
        if operator.value not in self.supported_ops:
            raise NotImplementedError(f"Operator {operator.value} is not supported for field {self.field}")
        return BaseCondition(self.field, operator, other)

    method.__name__ = operator.value
    return method


class ConditionFactory(Generic[ValueT]):
    def __init__(self, field: str, supported_ops: list[str]):
        self.field = field
        self.supported_ops = supported_ops

    __eq__ = condition_method(Operator.EQ)
    __gt__ = condition_method(Operator.GT)
    __ge__ = condition_method(Operator.GE)
    __lt__ = condition_method(Operator.LT)
    __le__ = condition_method(Operator.LE)


class CommunityConditionFactory:
    def has(self, *community: str) -> BaseCondition[list[str]]:
        return BaseCondition("community", Operator.HAS, community)

    def has_any(self, *community: str) -> BaseCondition[list[str]]:
        return BaseCondition("community", Operator.HAS_ANY, community)


class Checkable:
    def __init__(self):
        self.community = CommunityConditionFactory()
        self.interface = ConditionFactory[str]("interface", ["=="])
        self.protocol = ConditionFactory[str]("protocol", ["=="])
        self.as_path_length = ConditionFactory[int]("as_path_length", ["==", ">="])


R = Checkable()
Condition = Union[BaseCondition, "AndCondition"]


class AndCondition:
    def __init__(self, *conditions: Condition):
        self.conditions: list[BaseCondition[Any]] = []
        for c in conditions:
            self.conditions.extend(self._unpack(c))
        self._check_duplicates()

    def _check_duplicates(self) -> None:
        seen_fields: set[str] = set()
        for condition in self.conditions:
            if condition.field in seen_fields:
                raise ValueError(f"Cannot have multiple condition on field {condition.field}")

    def _unpack(self, other: Condition) -> Sequence[BaseCondition]:
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

    def __getitem__(self, item: str):
        return next(c for c in self.conditions if c.field == item)

    def __contains__(self, item: str):
        return any(c.field == item for c in self.conditions)

    def __len__(self):
        return len(self.conditions)

    def __iter__(self) -> Iterator[BaseCondition[Any]]:
        return iter(self.conditions)
