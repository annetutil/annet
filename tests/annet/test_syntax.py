from collections import OrderedDict, defaultdict

import pytest

from annet.annlib.rbparser.syntax import parse_text


@pytest.mark.parametrize(
    "raw_rule, expected",
    [
        (
            "row%a %b=bb %c=2 %d %e=",
            OrderedDict(
                [
                    (
                        "row%a %b=bb %c=2 %d %e=",
                        {
                            "children": OrderedDict(),
                            "context": {},
                            "params": {
                                "a": "A", # no `a` present in rule, default value from schema
                                "b": "bb", # value from rule as is, `%` is preserved
                                "c": "2", # value from rule as is
                                "d": "1", # no value for `d` provided, default to `1`
                                "e": "1", # no value for `e` provided, default to `1`
                            },
                            "raw_rule": "row%a %b=bb %c=2 %d %e=",
                            "row": "row%a",
                            "type": "normal",
                        },
                    )
                ],
            ),
        ),
        (
            "row1 row2 %a=x y z %b %c/42",
            OrderedDict(
                [
                    (
                        "row1 row2 %a=x y z %b %c/42",
                        {
                            "children": OrderedDict(),
                            "context": {},
                            "params": {
                                "a": "x y z",
                                "b": "1",
                                "c": "C", # no `c` found, since `%c/42` is not recognized as param
                                "d": "D",
                                "e": "E",
                            },
                            "raw_rule": "row1 row2 %a=x y z %b %c/42",
                            "row": "row1 row2",
                            "type": "normal",
                        },
                    )
                ],
            ),
        ),
    ],
)
def test_parse_text(raw_rule, expected) -> None:
    result = parse_text(raw_rule, {})
    assert (
        parse_text(
            raw_rule,
            {
                "a": {"validator": lambda v: v, "default": "A"},
                "b": {"validator": lambda v: v, "default": "B"},
                "c": {"validator": lambda v: v, "default": "C"},
                "d": {"validator": lambda v: v, "default": "D"},
                "e": {"validator": lambda v: v, "default": "E"},
            },
        )
        == expected
    )
