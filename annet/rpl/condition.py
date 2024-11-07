from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar, Sequence, Union, Callable


class Operator(Enum):
    EQ = "=="
    GE = ">="
    GT = ">"
    LE = "<="
    LT = "<"


ValueT = TypeVar("ValueT")


@dataclass(frozen=True)
class BaseCondition(Generic[ValueT]):
    field: str
    operator: Operator
    value: ValueT

    def __and__(self, other: "Condition") -> "AndCondition":
        return AndCondition(self, other)


@dataclass(frozen=True)
class CommunityCondition:
    values: Sequence[str]

    def __and__(self, other: "Condition") -> "AndCondition":
        return AndCondition(self, other)


_ConditionMethod = Callable[["ConditionFactory[ValueT]", ValueT], BaseCondition[ValueT]]


def condition(operator: Operator) -> _ConditionMethod:
    def method(self: "ConditionFactory[ValueT]", other: ValueT) -> BaseCondition[ValueT]:
        return BaseCondition(self.field, operator, other)

    method.__name__ = operator.value
    return method


class ConditionFactory(Generic[ValueT]):
    def __init__(self, field: str):
        self.field = field

    __eq__ = condition(Operator.EQ)
    __gt__ = condition(Operator.GT)
    __ge__ = condition(Operator.GE)
    __lt__ = condition(Operator.LT)
    __le__ = condition(Operator.LE)


class CommunityConditionFactory:
    def has(self, *community: str) -> CommunityCondition:
        return CommunityCondition(community)


class Checkable:
    def __init__(self):
        self.community = CommunityConditionFactory()
        self.interface = ConditionFactory[str]("interface")
        self.protocol = ConditionFactory[str]("protocol")
        self.as_path_length = ConditionFactory[int]("as_path_length")


R = Checkable()
SingleCondition = Union[BaseCondition, CommunityCondition]
Condition = Union[BaseCondition, CommunityCondition, "AndCondition"]


class AndCondition:
    def __init__(self, *conditions: Condition):
        self.conditions = []
        for c in conditions:
            self.conditions.extend(self._unpack(c))

    def _unpack(self, other: Condition) -> Sequence[SingleCondition]:
        if isinstance(other, AndCondition):
            return other.conditions
        return [other]

    def __and__(self, other: Condition) -> "AndCondition":
        return AndCondition(*self.conditions, other)

    def __iadd__(self, other):
        self.conditions.extend(self._unpack(other))
