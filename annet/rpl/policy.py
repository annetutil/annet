from dataclasses import dataclass

from .action import Action
from .condition import AndCondition
from .result import ResultType


@dataclass
class RoutingPolicyStatement:
    name: str
    number: int
    match: AndCondition
    then: Action
    result: ResultType


@dataclass
class RoutingPolicyTuple:
    name: str
    statements: tuple[RoutingPolicyStatement]
