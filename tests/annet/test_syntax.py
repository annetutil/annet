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
    "row, expected_pattern, line, should_match",
    [
        # --- ?/{regex}/ ---------------------------------------------------------
        # ?/{regex}/ matches without capturing, and the regexp is protected from
        # placeholder substitution (the inner * and (...) stay part of the regexp).
        ("?/(.*)/permit ~", r"^(?:(?:.*))permit\s+(.+)", "0 permit udp any 10.212.32.224 0.0.0.31", True),
        ("?/(.*)/permit ~", r"^(?:(?:.*))permit\s+(.+)", "0 deny udp any", False),
        ("?/permit|deny/ ~", r"^(?:permit|deny)\s+(.+)", "permit udp any", True),
        ("?/permit|deny/ ~", r"^(?:permit|deny)\s+(.+)", "remark something", False),
        ("ip ?/v4|v6/ route ~", r"^ip\s+(?:v4|v6)\s+route\s+(.+)", "ip v6 route ::/0", True),
        ("ip ?/v4|v6/ route ~", r"^ip\s+(?:v4|v6)\s+route\s+(.+)", "ip v8 route x", False),
        # without ? prefix literal slashes are treated like regular characters
        ("interface Eth0/0/1", r"^interface\s+Eth0/0/1(?:\s|$)", "interface Eth0/0/1", True),
        ("interface Eth0/0/1", r"^interface\s+Eth0/0/1(?:\s|$)", "interface Eth0X0X1", False),
        # combines with the case-insensitive prefix (which is stripped into a flag)
        ("(?i)?/INT.*/ ~", r"^(?:INT.*)\s+(.+)", "Interface foo", True),
        # glued to following text, no trailing ~: still closes at the first /
        ("?/(.*)/permit", r"^(?:(?:.*))permit(?:\s|$)", "permit", True),
        ("?/(.*)/permit", r"^(?:(?:.*))permit(?:\s|$)", "deny", False),
        # --- ~/{regex}/ ---------------------------------------------------------
        # ~/{regex}/ is wrapped in (?:...) so a top-level alternation does not leak
        # into the rest of the row.
        ("~/a|b/ x", r"^(?:a|b)\s+x", "a x", True),
        ("~/a|b/ x", r"^(?:a|b)\s+x", "b x", True),
        ("~/a|b/ x", r"^(?:a|b)\s+x", "c x", False),
        # the regexp ends at its own first /, so literal slashes after it stay intact
        ("~/interface|if/ eth0/1/2", r"^(?:interface|if)\s+eth0/1/2", "if eth0/1/2", True),
        ("~/interface|if/ eth0/1/2", r"^(?:interface|if)\s+eth0/1/2", "if eth0X1X2", False),
        # several ~/.../ on one row do not bleed into each other
        ("~/a|b/ x ~/c|d/", r"^(?:a|b)\s+x\s+(?:c|d)", "a x d", True),
        ("~/a|b/ x ~/c|d/", r"^(?:a|b)\s+x\s+(?:c|d)", "a x e", False),
        # --- ?/{regex}/ and ~/{regex}/ mixed ------------------------------------
        # several placeholders on one row do not bleed into each other: each one
        # ends at its own first /, and the ~/x/ in between stays intact.
        ("?/a|b/ ~/x/ ?/y|z/", r"^(?:a|b)\s+(?:x)\s+(?:y|z)", "a x y", True),
        ("?/a|b/ ~/x/ ?/y|z/", r"^(?:a|b)\s+(?:x)\s+(?:y|z)", "b x z", True),
        ("?/a|b/ ~/x/ ?/y|z/", r"^(?:a|b)\s+(?:x)\s+(?:y|z)", "a q y", False),
        ("?/a|b/ ~/x/ ?/y|z/", r"^(?:a|b)\s+(?:x)\s+(?:y|z)", "a x q", False),
    ],
)
def test_compile_row_regexp(row, expected_pattern, line, should_match) -> None:
    compiled = compile_row_regexp(row)
    assert compiled.pattern == expected_pattern
    assert bool(compiled.match(line)) is should_match


def test_compile_row_regexp_noncapturing_has_no_extra_groups() -> None:
    # Only the trailing `~` contributes a capture group; ?/(.*)/ captures nothing.
    assert compile_row_regexp("?/(.*)/permit ~").groups == 1
    assert compile_row_regexp("?/(.*)/permit").groups == 0
