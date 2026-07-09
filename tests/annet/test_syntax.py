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
        # A ~/{regex}/ runs greedily to the LAST / on the row, so the regexp may itself
        # contain literal slashes -- e.g. ~/(GE.+?/[12](\.|$))/ matching GE1/0/2.
        (
            r"interface ~/(GE.+?/[12](\.|$))/",
            r"^interface\s+((?:GE.+?/[12](?:\.|$)))",
            "interface GE1/0/2",
            True,
        ),
        (
            r"interface ~/(GE.+?/[12](\.|$))/",
            r"^interface\s+((?:GE.+?/[12](?:\.|$)))",
            "interface GE1/0/1",
            True,
        ),
        (
            r"interface ~/(GE.+?/[12](\.|$))/",
            r"^interface\s+((?:GE.+?/[12](?:\.|$)))",
            "interface GE1/0/3",
            False,
        ),
        (
            r"interface ~/(GE.+?/[12](\.|$))/",
            r"^interface\s+((?:GE.+?/[12](?:\.|$)))",
            "interface XE1/0/2",
            False,
        ),
        # Only ONE ?/ or ~/ regexp placeholder per row: the regexp is matched greedily to
        # the last /, so two placeholders do NOT split -- they merge into one capture. Put
        # everything in a single regexp instead.
        (r"~/a/ ~/b/", r"^(a/ ~/b)", "a/ ~/b", True),
        # The merged single-regexp form of `interface {downlinks}{vlans} mode l2` (what the
        # generator now emits -- downlinks and vlans combined into one ~/.../):
        (
            r"interface ~/((25GE.+?/[12](\.|$))([2-9]|[1-9]\d{1,2}|to))/ mode l2",
            r"^interface\s+((?:(25GE.+?/[12](?:\.|$))(?:[2-9]|[1-9]\d{1,2}|to)))\s+mode\s+l2(?:\s|$)",
            "interface 25GE1/0/2.134 mode l2",
            True,
        ),
        (
            r"interface ~/((25GE.+?/[12](\.|$))([2-9]|[1-9]\d{1,2}|to))/ mode l2",
            r"^interface\s+((?:(25GE.+?/[12](?:\.|$))(?:[2-9]|[1-9]\d{1,2}|to)))\s+mode\s+l2(?:\s|$)",
            "interface 25GE1/0/3.134 mode l2",
            False,
        ),
        # ~/{regex}/ also works when combined with a trailing ~
        ("~/(a|b)/ permit ~", r"^((?:a|b))\s+permit\s+(.+)", "a permit foo bar", True),
        ("~/(a|b)/ permit ~", r"^((?:a|b))\s+permit\s+(.+)", "c permit foo", False),
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
        # a trailing placeholder is NOT anchored: the regexp owns the right edge, so the
        # line may continue past the match (here just the bare token, but cf. subinterfaces)
        ("~/c|d/", r"^(c|d)", "d", True),
        ("~/c|d/", r"^(c|d)", "e", False),
        # --- hand-written trailing lookaround -----------------------------------
        # A row that ends in a hand-written zero-width lookaround (never a placeholder)
        # is likewise NOT anchored. Used by ACLs like
        # `interface (?!25GE.+?/...|Vbdif(~/(52[1-9]\d{4})/))` to cover any interface
        # whose name is not one of the excluded ones. A ~/.../ placeholder may be nested
        # inside the lookaround (preceded by `(`), so it is still unwrapped.
        (
            r"interface (?!25GE.+?/([^12](\.|$)|\d{2}(\.|$))|Vbdif(~/(52[1-9]\d{4})/))",
            r"^interface\s+(?!25GE.+?/([^12](\.|$)|\d{2}(\.|$))|Vbdif(((?:52[1-9]\d{4}))))",
            "interface 100GE1/0/1",
            True,
        ),
        (
            r"interface (?!25GE.+?/([^12](\.|$)|\d{2}(\.|$))|Vbdif(~/(52[1-9]\d{4})/))",
            r"^interface\s+(?!25GE.+?/([^12](\.|$)|\d{2}(\.|$))|Vbdif(((?:52[1-9]\d{4}))))",
            "interface 25GE1/0/3",
            False,
        ),
        (
            r"interface (?!25GE.+?/([^12](\.|$)|\d{2}(\.|$))|Vbdif(~/(52[1-9]\d{4})/))",
            r"^interface\s+(?!25GE.+?/([^12](\.|$)|\d{2}(\.|$))|Vbdif(((?:52[1-9]\d{4}))))",
            "interface Vbdif5210000",
            False,
        ),
        # a placeholder nested in a (?!...) lookahead is unwrapped, and the lookahead
        # tail is left un-anchored
        (
            r"interface Vbdif(?!~/(52[1-9]\d{4})/)",
            r"^interface\s+Vbdif(?!((?:52[1-9]\d{4})))",
            "interface Vbdif100",
            True,
        ),
        (
            r"interface Vbdif(?!~/(52[1-9]\d{4})/)",
            r"^interface\s+Vbdif(?!((?:52[1-9]\d{4})))",
            "interface Vbdif5210000",
            False,
        ),
        # a trailing consuming group (NOT a lookaround) keeps the anchor, so it matches a
        # whole token: interface (eth|lo) matches "interface eth", not "interface ethernet".
        ("interface (eth|lo)", r"^interface\s+(eth|lo)(?:\s|$)", "interface eth", True),
        ("interface (eth|lo)", r"^interface\s+(eth|lo)(?:\s|$)", "interface ethernet", False),
        ("user (RO|SU)", r"^user\s+(RO|SU)(?:\s|$)", "user RO", True),
        ("user (RO|SU)", r"^user\s+(RO|SU)(?:\s|$)", "user ROOT", False),
        # Un-anchoring keys off ~/ presence (the pre-?/{regex}/ rule), not lookaround
        # detection. A hand-written lookaround that nests a ~/ -- as production negative
        # ACLs always do, via api_id_prefix / Vbdif(~/.../) -- is un-anchored (see the
        # `interface (?!...|Vbdif(~/.../))` case above). A BARE (?!...) with no ~/ is
        # treated like any other group and stays anchored (so it matches nothing useful --
        # write the lookaround through a ~/ placeholder).
        ("interface (?!Eth)", r"^interface\s+(?!Eth)(?:\s|$)", "interface Gi0", False),
        # a trailing literal token (even after a placeholder) still anchors: ?/(.*)/permit
        # matches the whole token `permit`, not `permitxxx`.
        ("?/(.*)/permit", r"^(?:(?:.*))permit(?:\s|$)", "permit", True),
        ("?/(.*)/permit", r"^(?:(?:.*))permit(?:\s|$)", "permitxxx", False),
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
