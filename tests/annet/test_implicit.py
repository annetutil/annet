from collections import OrderedDict as odict

import pytest

from annet import implicit, tabparser

from .. import make_hw_stub


VENDOR = "huawei"


@pytest.fixture
def empty_config():
    formater = tabparser.make_formatter(make_hw_stub(VENDOR))
    return tabparser.parse_to_tree("", splitter=formater.split)


@pytest.fixture
def config():
    formater = tabparser.make_formatter(make_hw_stub(VENDOR))
    return tabparser.parse_to_tree("""
        section_1
        section_2
    """, splitter=formater.split)


@pytest.fixture
def add_nothing():
    return implicit.compile_tree(implicit.parse_text(""))


@pytest.fixture
def implicit_rules():
    return implicit.compile_tree(implicit.parse_text("""
        !section_1
            added_subcommand
        added_command
    """))


def text_empty_implicit(config, add_nothing):
    assert implicit.config(config, add_nothing) == odict()


def test_empty_config(empty_config, implicit_rules):
    assert implicit.config(empty_config, implicit_rules) == odict([
        ("added_command", odict())
    ])


def test_subcommand(config, implicit_rules):
    assert implicit.config(config, implicit_rules) == odict([
        ("section_1",
            odict([("added_subcommand", odict())])
         ),
        ("added_command", odict())
    ])
