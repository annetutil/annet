from collections import OrderedDict as odict
from textwrap import dedent

import pytest

from annet.patching import PatchTree, make_diff
from annet.rulebook.common import default, default_diff, ordered_diff
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
    import re

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


def _make_match(rb, *key):
    return {
        "attrs": rb["patching"]["global"]["~"]["attrs"],
        "raw_rule": "~",
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
