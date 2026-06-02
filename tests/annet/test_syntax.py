from collections import OrderedDict

import pytest

from annet.annlib.rbparser.syntax import compile_row_regexp, parse_text


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
                                "a": "A",  # no `a` present in rule, default value from schema
                                "b": "bb",  # value from rule as is, `%` is preserved
                                "c": "2",  # value from rule as is
                                "d": "1",  # no value for `d` provided, default to `1`
                                "e": "1",  # no value for `e` provided, default to `1`
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
                                "c": "C",  # no `c` found, since `%c/42` is not recognized as param
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


@pytest.mark.parametrize(
    "row, line, should_match",
    [
        # ?/{regex}/ matches without capturing, and the regexp is protected from
        # placeholder substitution (the inner * and (...) stay part of the regexp).
        ("?/(.*)/permit ~", "0 permit udp any 10.212.32.224 0.0.0.31", True),
        ("?/(.*)/permit ~", "0 deny udp any", False),
        ("?/permit|deny/ ~", "permit udp any", True),
        ("?/permit|deny/ ~", "remark something", False),
        ("ip ?/v4|v6/ route ~", "ip v6 route ::/0", True),
        ("ip ?/v4|v6/ route ~", "ip v8 route x", False),
        # the ? prefix keeps literal slashes (e.g. interface names) intact
        ("interface Eth0/0/1", "interface Eth0/0/1", True),
        ("interface Eth0/0/1", "interface Eth0X0X1", False),
        # combines with the case-insensitive prefix
        ("(?i)?/INT.*/ ~", "Interface foo", True),
    ],
)
def test_compile_row_regexp_noncapturing_match(row, line, should_match) -> None:
    assert bool(compile_row_regexp(row).match(line)) is should_match


def test_compile_row_regexp_noncapturing_has_no_extra_groups() -> None:
    # Only the trailing `~` contributes a capture group; ?/(.*)/ captures nothing.
    assert compile_row_regexp("?/(.*)/permit ~").groups == 1
    assert compile_row_regexp("?/(.*)/permit").groups == 0
