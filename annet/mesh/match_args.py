import re
from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

MatchedArgs = SimpleNamespace


class MatchExpr:
    def __init__(self, expr: Callable):
        self.expr = expr

    def __getattr__(self, item: str):
        return MatchExpr(lambda x: getattr(self.expr(x), item))

    def __getitem__(self, item: str):
        return MatchExpr(lambda x: self.expr(x)[item])

    def __eq__(self, other) -> "MatchExpr":
        if isinstance(other, MatchExpr):
            return MatchExpr(lambda x: self.expr(x) == other.expr(x))
        else:
            return MatchExpr(lambda x: self.expr(x) == other)

    def __lt__(self, other) -> "MatchExpr":
        if isinstance(other, MatchExpr):
            return MatchExpr(lambda x: self.expr(x) < other.expr(x))
        else:
            return MatchExpr(lambda x: self.expr(x) < other)

    def __gt__(self, other) -> "MatchExpr":
        if isinstance(other, MatchExpr):
            return MatchExpr(lambda x: self.expr(x) > other.expr(x))
        else:
            return MatchExpr(lambda x: self.expr(x) > other)

    def __le__(self, other) -> "MatchExpr":
        if isinstance(other, MatchExpr):
            return MatchExpr(lambda x: self.expr(x) <= other.expr(x))
        else:
            return MatchExpr(lambda x: self.expr(x) <= other)

    def __ge__(self, other) -> "MatchExpr":
        if isinstance(other, MatchExpr):
            return MatchExpr(lambda x: self.expr(x) >= other.expr(x))
        else:
            return MatchExpr(lambda x: self.expr(x) >= other)

    def __or__(self, other: "MatchExpr") -> "MatchExpr":
        return MatchExpr(lambda x: self.expr(x) or other.expr(x))

    def __and__(self, other: "MatchExpr") -> "MatchExpr":
        return MatchExpr(lambda x: self.expr(x) and other.expr(x))

    def cast_(self, type_: Callable[[Any], Any]) -> "MatchExpr":
        return MatchExpr(lambda x: type_(self.expr(x)))

    def in_(self, value: Any) -> "MatchExpr":
        if isinstance(value, MatchExpr):
            return MatchExpr(lambda x: self.expr(x) in value.expr(x))
        else:
            return MatchExpr(lambda x: self.expr(x) in value)


Left = MatchExpr(lambda x: x[0])
Right = MatchExpr(lambda x: x[1])


class PeerNameTemplate:
    def __init__(self, raw_str):
        self._str = str(raw_str)
        self._regex, self._types = self._compile(self._str)

    def __str__(self):
        return self._str

    @staticmethod
    def _compile(value: str) -> tuple[re.Pattern[str], dict[str, type]]:
        int_groups = re.findall(r'{(?P<group_name>\w+)}', value)
        # '{name}'  -> (?P<name>\d+)
        regex_string = re.sub(r"{(?P<group_name>\w+)}", r"(?P<\g<group_name>>\\d+)", value)
        # '{name:regex}' -> (?P<name>regex)
        regex_string = re.sub(
            r"{(?P<group_name>\w+):(?P<custom_regex>.*?)}", r"(?P<\g<group_name>>\g<custom_regex>)",
            regex_string
        )
        pattern = re.compile(regex_string)
        types = {
            name: (int if name in int_groups else str)
            for name in pattern.groupindex
        }
        return pattern, types

    def match(self, hostname: str) -> dict[str, str] | None:
        reg_match = self._regex.match(hostname)
        if reg_match:
            return {
                key: self._types[key](value)
                for key, value in reg_match.groupdict().items()
            }
        return None


def match_safe(matcher: MatchExpr | None, value: Any) -> bool:
    if matcher is None:
        return True
    try:
        return bool(matcher.expr(value))
    except (TypeError, ValueError, AttributeError, KeyError, IndexError):
        return False


@dataclass
class SingleMatcher:
    def __init__(self, rule: str, match_expr: MatchExpr | None):
        self.rule = PeerNameTemplate(rule)
        self.match_expr = match_expr

    def _match_host(self, rule: PeerNameTemplate, host) -> MatchedArgs | None:
        data = rule.match(host)
        if data is None:
            return None
        return MatchedArgs(**data)

    def match_one(self, host) -> MatchedArgs | None:
        args = self._match_host(self.rule, host)
        if args is None:
            return None
        if not match_safe(self.match_expr, (args,)):
            return None
        return args


@dataclass
class PairMatcher:
    def __init__(self, left_rule: str, right_rule: str, match_expr: MatchExpr | None):
        self.left_rule = PeerNameTemplate(left_rule)
        self.right_rule = PeerNameTemplate(right_rule)
        self.match_expr = match_expr

    def match_pair(self, left, right) -> tuple[MatchedArgs, MatchedArgs] | None:
        left_args = self._match_host(self.left_rule, left)
        if left_args is None:
            return None
        right_args = self._match_host(self.right_rule, right)
        if right_args is None:
            return None
        if not match_safe(self.match_expr, (left_args, right_args)):
            return None
        return left_args, right_args

    def _match_host(self, rule: PeerNameTemplate, host) -> MatchedArgs | None:
        data = rule.match(host)
        if data is None:
            return None
        return MatchedArgs(**data)
