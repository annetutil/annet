import re
from collections import OrderedDict as odict
from textwrap import dedent

import pytest

from annet.annlib.patching import Orderer
from annet.annlib.rbparser import syntax
from annet.annlib.rbparser.ordering import compile_ordering_text
from annet.patching import PatchTree, make_diff
from annet.rulebook.common import default, default_diff, ordered_diff
from annet.rulebook.patching import _make_reverse
from annet.types import Op
from annet.vendors.tabparser import CommonFormatter


@pytest.fixture
def empty_config_tree():
    return odict()


@pytest.fixture
def config_tree():
    return odict([("z", {}), ("a", odict([("b", {})]))])


@pytest.fixture
def reversed_tree(config_tree):
    return odict(reversed(list(config_tree.items())))


@pytest.fixture
def rb(request):
    return {
        "patching": {
            "local": odict(),
            "global": odict(
                [
                    (
                        "~",
                        {
                            "attrs": {
                                "logic": default,
                                "diff_logic": request.param,
                                "direct": True,
                                "regexp": re.compile(r"^([^\s]+)"),
                                "multiline": False,
                                "ignore_case": False,
                            },
                            "children": {"global": odict(), "local": odict()},
                            "type": "normal",
                            "rule": "~",
                        },
                    ),
                ]
            ),
        },
    }


@pytest.mark.parametrize("rb", [default_diff, ordered_diff], indirect=["rb"])
def test_diff_keeping_order(empty_config_tree, config_tree, rb):
    assert make_diff(empty_config_tree, config_tree, rb, []) == [
        (Op.ADDED, "z", [], _make_match(rb, "z")),
        (
            Op.ADDED,
            "a",
            [
                (Op.ADDED, "b", [], _make_match(rb, "b")),
            ],
            _make_match(rb, "a"),
        ),
    ]


@pytest.mark.parametrize("rb", [ordered_diff], indirect=["rb"])
def test_ordered_diff_block(config_tree, reversed_tree, rb):
    assert make_diff(config_tree, reversed_tree, rb, []) == [
        (
            Op.MOVED,
            "a",
            [
                (Op.MOVED, "b", [], _make_match(rb, "b")),
            ],
            _make_match(rb, "a"),
        ),
        (Op.MOVED, "z", [], _make_match(rb, "z")),
    ]


def _order_undos(rules):
    """Order an interface block containing `undo eth-trunk` and `undo portswitch` (in that, reversed,
    order) and return the resulting sequence of commands."""
    orderer = Orderer(compile_ordering_text(dedent(rules), "huawei"), "huawei")
    config = odict(
        [
            (
                "interface X",
                odict(
                    [
                        ("undo eth-trunk", odict()),
                        ("undo portswitch", odict()),
                    ]
                ),
            ),
        ]
    )
    return list(orderer.order_config(config)["interface X"])


def test_undo_reverse_ordered_by_default():
    # A bare reverse command is reverse-ordered: a line written later in the rulebook is applied
    # earlier, so `undo eth-trunk` ends up before `undo portswitch`.
    assert _order_undos("""
        interface *
            undo portswitch
            undo eth-trunk
    """) == ["undo eth-trunk", "undo portswitch"]


def test_order_reverse_pins_undo_forward():
    # %order_reverse cancels the reversal and pins the `undo` command at its written position, so the
    # rulebook order is honored: `undo portswitch` before `undo eth-trunk`.
    assert _order_undos("""
        interface *
            undo portswitch  %order_reverse
            undo eth-trunk   %order_reverse
    """) == ["undo portswitch", "undo eth-trunk"]


def test_order_reverse_on_direct_row_is_a_noop():
    # %order_reverse only has an effect on a row that is itself an `undo ...` command. On a direct row
    # it matches nothing, leaving the reverse command unordered (falls back to position 0).
    orderer = Orderer(
        compile_ordering_text(
            dedent("""
        interface *
            aaa
            bbb
            portswitch  %order_reverse
    """),
            "huawei",
        ),
        "huawei",
    )
    pos = orderer.get_order(("interface X", "undo portswitch"), cmd_direct=False)
    assert pos[0][-1][0] == 0


def _make_match(rb, *key):
    return {
        "attrs": rb["patching"]["global"]["~"]["attrs"],
        "raw_rule": "~",
        "rule": "~",
        "key": key,
    }


def test_patch_class_tree_asdict():
    tree = PatchTree()
    assert not tree
    assert tree.asdict() == {}
    tree.add("a", {})
    assert tree.asdict() == {"a": None}
    tree.add_block("a", PatchTree("b"))
    assert tree.asdict() == {"a": {"b": None}}
    tree.add_block("a", PatchTree("c"))
    assert tree.asdict() == {"a": {"b": None, "c": None}}


def test_patch_class_tree():
    tree = PatchTree()
    tree.add_block("a").add("b", {})
    tree.add_block("a").add("c", {})
    fmtr = CommonFormatter("  ")
    assert fmtr.patch(tree) + "\n" == dedent("""\
    a
      b
    a
      c
    """)


def test_patch_class_to_from_json():
    tree = PatchTree()
    tree.add_block("a").add("b", {})
    tree.add_block("a").add("c", {})

    json = tree.to_json()
    assert json == PatchTree.from_json(json).to_json()


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        # plain word/tail captures keep one {} each
        ("snmp-agent sys-info *", "no snmp-agent sys-info {}"),
        ("* permit ~", "no {} permit {}"),
        # */{regex}/ and ~/{regex}/ are both capturing -> one {} each
        ("*/(.*)/permit ~", "no {}permit {}"),
        ("*/syslog-level/ ~/(emergency|alert|info)/ *", "no {} {} {}"),
        ("~/(a|b)/ permit", "no {} permit"),
        ("~/(a|b)/ permit ~", "no {} permit {}"),
        # ?/{regex}/ is non-capturing -> no {}, and the * inside it must not leak out
        ("?/(.*)/permit ~", "no permit {}"),
        # the * inside a ~/{regex}/ regexp must not leak out as an extra {}
        ("~/(a*)/permit ~", "no {}permit {}"),
        # an existing reverse prefix is stripped rather than doubled
        ("no permit *", "permit {}"),
    ],
)
def test_make_reverse(row, expected):
    reverse = _make_reverse(row, "no")
    assert reverse == expected
    # the number of {} must match the number of capturing groups produced for the
    # row, since reverse.format(*match.groups()) relies on that invariant
    assert reverse.count("{}") == syntax.compile_row_regexp(row).groups
