from collections import OrderedDict as odict
from unittest import mock

import pytest

from annet import implicit
from annet.vendors import registry_connector, tabparser

from .. import make_hw_stub


VENDOR = "huawei"
VENDOR_ROS = "routeros"


@pytest.fixture
def empty_config():
    formater = registry_connector.get().match(make_hw_stub(VENDOR)).make_formatter()
    return tabparser.parse_to_tree("", splitter=formater.split)


@pytest.fixture
def config():
    formater = registry_connector.get().match(make_hw_stub(VENDOR)).make_formatter()
    return tabparser.parse_to_tree(
        """
        section_1
        section_2
    """,
        splitter=formater.split,
    )


@pytest.fixture
def add_nothing():
    return implicit.compile_tree(implicit.parse_text(""))


@pytest.fixture
def implicit_rules():
    return implicit.compile_tree(
        implicit.parse_text("""
        !section_1
            added_subcommand
        added_command
    """)
    )


def text_empty_implicit(config, add_nothing):
    assert implicit.config(config, add_nothing) == odict()


def test_empty_config(empty_config, implicit_rules):
    assert implicit.config(empty_config, implicit_rules) == odict([("added_command", odict())])


def test_subcommand(config, implicit_rules):
    assert implicit.config(config, implicit_rules) == odict(
        [
            ("section_1", odict([("added_subcommand", odict())])),
            ("added_command", odict()),
        ]
    )


# ====== RouterOS tests ======


@pytest.fixture
def ros_empty_config():
    formatter = registry_connector.get().match(make_hw_stub(VENDOR_ROS)).make_formatter()
    return tabparser.parse_to_tree("", splitter=formatter.split)


@pytest.fixture
def ros_config_enabled_no():
    formatter = registry_connector.get().match(make_hw_stub(VENDOR_ROS)).make_formatter()
    return tabparser.parse_to_tree(
        "/tool mac-server ping\nset enabled=no",
        splitter=formatter.split,
    )


def test_ros_implicit_adds_default(ros_empty_config):
    """If set enabled is not specified — implicit adds set enabled=yes"""
    rules = implicit.compile_rules(mock.Mock(hw=make_hw_stub(VENDOR_ROS)))
    result = implicit.config(ros_empty_config, rules)
    assert result["tool"]["mac-server"]["ping"]["set enabled=yes"] == odict()


def test_ros_implicit_no_override_when_disabled(ros_config_enabled_no):
    """If set enabled=no — implicit does NOT add set enabled=yes"""
    rules = implicit.compile_rules(mock.Mock(hw=make_hw_stub(VENDOR_ROS)))
    result = implicit.config(ros_config_enabled_no, rules)
    ping = result.get("tool", {}).get("mac-server", {}).get("ping", {})
    assert "set enabled=yes" not in ping
