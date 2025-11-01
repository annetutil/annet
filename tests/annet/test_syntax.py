from collections import OrderedDict, defaultdict

import pytest

from annet.annlib.rbparser.syntax import parse_text


@pytest.mark.parametrize(
    "raw_rule, expected",
    [
        (
            "row%a %b=%B %c=2 %d %e=",
            OrderedDict(
                [
                    (
                        "row%a %b=%B %c=2 %d %e=",
                        {
                            "children": OrderedDict(),
                            "context": {},
                            "params": {
                                "a": "A", # no `a` present in rule, default value from schema
                                "b": "%B", # value from rule as is, `%` is preserved
                                "c": "2", # value from rule as is
                                "d": "1", # no value for `d` provided, default to `1`
                                "e": "1", # no value for `e` provided, default to `1`
                            },
                            "raw_rule": "row%a %b=%B %c=2 %d %e=",
                            "row": "row%a",
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
