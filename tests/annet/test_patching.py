import re
from collections import OrderedDict as odict
from textwrap import dedent

import pytest

from annet.annlib.rbparser import syntax
from annet.patching import PatchTree, make_diff, make_patch, make_pre
from annet.rulebook.common import default, default_diff, ordered_diff
from annet.rulebook.patching import _make_reverse, compile_patching_text
from annet.types import Op
from annet.vendors.tabparser import CommonFormatter

from .. import make_hw_stub


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


def custom_diff_logic(old, new, diff_pre, _pops=(Op.AFFECTED,)):
    """Behaves exactly like the default logic, it is only a distinct function object"""
    return default_diff(old, new, diff_pre, _pops)


def test_diff_keeps_block_order_with_mixed_diff_logic():
    """A rule with its own %diff_logic must not regroup the block it matches in - #638"""
    rb_text = dedent("""
        ip access-list ~
            ?/(\\d+)/ permit ~   %diff_logic=tests.annet.test_patching.custom_diff_logic
            ~
    """).strip()
    rb = {"patching": compile_patching_text(rb_text, "cisco")}

    def acl(*rows):
        return odict([("ip access-list extended TEST", odict((row, odict()) for row in rows))])

    old = acl("10 permit ip any any")
    new = acl(
        "20 deny ip host 0.0.0.0 any",
        "30 permit tcp any any eq 22",
        "60 remark GRE",
        "70 permit gre any any",
        "230 deny ip any any log",
    )

    [(op, row, children, _match)] = make_diff(old, new, rb, [])
    assert (op, row) == (Op.AFFECTED, "ip access-list extended TEST")
    # the permits are matched by the custom rule and the rest by the plain one,
    # but both groups keep their places in the block
    assert [(child_op, child_row) for child_op, child_row, _, _ in children] == [
        (Op.REMOVED, "10 permit ip any any"),
        (Op.ADDED, "20 deny ip host 0.0.0.0 any"),
        (Op.ADDED, "30 permit tcp any any eq 22"),
        (Op.ADDED, "60 remark GRE"),
        (Op.ADDED, "70 permit gre any any"),
        (Op.ADDED, "230 deny ip any any log"),
    ]


def test_patch_keeps_block_order_when_rows_match_different_rules(ann_connectors):
    """The patch must follow the config, not the rulebook rule that matched each row - #638"""
    rb_text = dedent("""
        ip access-list ~
            ?/(\\d+)/ remark ~   %diff_logic=tests.annet.test_patching.custom_diff_logic
            ~
    """).strip()
    rb = {"patching": compile_patching_text(rb_text, "cisco"), "ordering": {}}
    hw = make_hw_stub("cisco")

    old = odict([("ip access-list extended TEST", odict())])
    new = odict(
        [
            (
                "ip access-list extended TEST",
                odict(
                    (row, odict())
                    for row in [
                        "10 remark SSH",
                        "20 permit tcp any any eq 22",
                        "30 remark GRE",
                        "40 permit gre any any",
                        "50 remark DENY",
                        "60 deny ip any any log",
                    ]
                ),
            )
        ]
    )

    diff = make_diff(old, new, rb, [])
    patch = make_patch(pre=make_pre(diff), rb=rb, hw=hw, add_comments=False)
    # the remarks are matched by their own rule and the rest by the plain one,
    # yet the acl is written out in the order it was generated in
    assert list(patch.asdict()["ip access-list extended TEST"]) == [
        "10 remark SSH",
        "20 permit tcp any any eq 22",
        "30 remark GRE",
        "40 permit gre any any",
        "50 remark DENY",
        "60 deny ip any any log",
    ]


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
