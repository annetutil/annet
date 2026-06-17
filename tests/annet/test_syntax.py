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
        # ~/{regex}/ captures its whole matched span into a single group (any inner
        # group the user wrote collapses to non-capturing -- only the wrapper captures),
        # so a top-level alternation does not leak into the rest of the row either.
        ("~/a|b/ x", r"^(a|b)\s+x(?:\s|$)", "a x", True),
        ("~/a|b/ x", r"^(a|b)\s+x(?:\s|$)", "b x", True),
        ("~/a|b/ x", r"^(a|b)\s+x(?:\s|$)", "c x", False),
        # a placeholder followed by literal text closes at its own boundary / (the one
        # followed by whitespace), so literal slashes after it stay intact
        ("~/interface|if/ eth0/1/2", r"^(interface|if)\s+eth0/1/2(?:\s|$)", "if eth0/1/2", True),
        ("~/interface|if/ eth0/1/2", r"^(interface|if)\s+eth0/1/2(?:\s|$)", "if eth0X1X2", False),
        # the regexp may itself contain literal slashes: it closes at the last / when no
        # earlier / sits on a token boundary. Used by ACLs like
        # `interface ~/(GE.+?/[12](\.|$))/` matching interface names such as GE1/0/2.
        (
            r"interface ~/(GE.+?/[12](\.|$))/",
            r"^interface\s+((?:GE.+?/[12](?:\.|$)))(?:\s|$)",
            "interface GE1/0/2",
            True,
        ),
        (
            r"interface ~/(GE.+?/[12](\.|$))/",
            r"^interface\s+((?:GE.+?/[12](?:\.|$)))(?:\s|$)",
            "interface GE1/0/1",
            True,
        ),
        (
            r"interface ~/(GE.+?/[12](\.|$))/",
            r"^interface\s+((?:GE.+?/[12](?:\.|$)))(?:\s|$)",
            "interface GE1/0/3",
            False,
        ),
        (
            r"interface ~/(GE.+?/[12](\.|$))/",
            r"^interface\s+((?:GE.+?/[12](?:\.|$)))(?:\s|$)",
            "interface XE1/0/2",
            False,
        ),
        # a slash-containing regexp still does not bleed into a following placeholder
        (r"~/a/b/ ~/c/d/", r"^(a/b)\s+(c/d)(?:\s|$)", "a/b c/d", True),
        (r"~/a/b/ ~/c/d/", r"^(a/b)\s+(c/d)(?:\s|$)", "a/b c/e", False),
        # several ~/.../ on one row do not bleed into each other; each captures
        ("~/a|b/ x ~/c|d/", r"^(a|b)\s+x\s+(c|d)(?:\s|$)", "a x d", True),
        ("~/a|b/ x ~/c|d/", r"^(a|b)\s+x\s+(c|d)(?:\s|$)", "a x e", False),
        # ~/{regex}/ also works when combined with a trailing ~
        ("~/(a|b)/ permit ~", r"^((?:a|b))\s+permit\s+(.+)", "a permit foo bar", True),
        ("~/(a|b)/ permit ~", r"^((?:a|b))\s+permit\s+(.+)", "c permit foo", False),
        # --- ?/{regex}/ and ~/{regex}/ mixed ------------------------------------
        # several placeholders on one row do not bleed into each other: each one
        # ends at its own first /. The ?/.../ stay non-capturing, the ~/x/ captures.
        ("?/a|b/ ~/x/ ?/y|z/", r"^(?:a|b)\s+(x)\s+(?:y|z)(?:\s|$)", "a x y", True),
        ("?/a|b/ ~/x/ ?/y|z/", r"^(?:a|b)\s+(x)\s+(?:y|z)(?:\s|$)", "b x z", True),
        ("?/a|b/ ~/x/ ?/y|z/", r"^(?:a|b)\s+(x)\s+(?:y|z)(?:\s|$)", "a q y", False),
        ("?/a|b/ ~/x/ ?/y|z/", r"^(?:a|b)\s+(x)\s+(?:y|z)(?:\s|$)", "a x q", False),
        # --- trailing zero-width placeholder ------------------------------------
        # A trailing ~/{regex}/ or ?/{regex}/ whose regexp matches an empty span
        # (a bare negative lookahead) is NOT anchored with (?:\s|$): the anchor
        # would have to match at the start of the token and could never succeed.
        # Used by ACLs like `forwarding-options ~/(?!(sampling|port-mirroring))/`.
        ("~/(?!(sampling|port-mirroring))/", r"^((?!(?:sampling|port-mirroring)))", "enhanced-hash-key", True),
        ("~/(?!(sampling|port-mirroring))/", r"^((?!(?:sampling|port-mirroring)))", "sampling", False),
        ("~/(?!(sampling|port-mirroring))/", r"^((?!(?:sampling|port-mirroring)))", "port-mirroring", False),
        ("user ~/(?!RO|SU)/", r"^user\s+((?!RO|SU))", "user admin", True),
        ("user ~/(?!RO|SU)/", r"^user\s+((?!RO|SU))", "user RO", False),
        ("interface ?/(?!Tunnel)/", r"^interface\s+(?:(?!Tunnel))", "interface Eth0", True),
        ("interface ?/(?!Tunnel)/", r"^interface\s+(?:(?!Tunnel))", "interface Tunnel0", False),
        # a trailing placeholder that still consumes input keeps the (?:\s|$) anchor
        ("~/c|d/", r"^(c|d)(?:\s|$)", "d", True),
        ("~/c|d/", r"^(c|d)(?:\s|$)", "e", False),
    ],
)
def test_compile_row_regexp(row, expected_pattern, line, should_match) -> None:
    compiled = compile_row_regexp(row)
    assert compiled.pattern == expected_pattern
    assert bool(compiled.match(line)) is should_match


def test_compile_row_regexp_capturing_groups() -> None:
    # ?/{regex}/ captures nothing; ~/{regex}/ captures one group regardless of any
    # * elsewhere in the row; only the trailing `~` adds its own group.
    assert compile_row_regexp("?/(.*)/permit ~").groups == 1
    assert compile_row_regexp("?/(.*)/permit").groups == 0
    assert compile_row_regexp("~/(a|b)/ permit").groups == 1
    assert compile_row_regexp("~/(a|b)/ permit ~").groups == 2
    # the * that previously de-capturing-ized inner groups no longer affects ~/.../
    assert compile_row_regexp("*/x/ ~/(a|b)/ *").groups == 3
