from collections import OrderedDict

import pytest

from annet import patching, rulebook
from annet.annlib.rbparser.acl import compile_acl_text
from annet.vendors import registry_connector, tabparser

from . import MockDevice


@pytest.fixture
def device():
    return MockDevice("Huawei CE6870-48S6CQ-EI", "VRP V200R001C00SPC700 + V200R001SPH002", "vrp85")


@pytest.fixture
def acl(device):
    return compile_acl_text(
        r"""
        interface %cant_delete=1
            stays %cant_delete=1
            removed
        """,
        device.hw.vendor,
    )


@pytest.fixture
def config(device):
    return r"""
        interface ge1/1/1
            stays
            removed
    """


def test_cant_delete_subblock(config, acl, device):
    formatter = registry_connector.get().match(device.hw).make_formatter()
    empty_tree = tabparser.parse_to_tree("", formatter.split)
    current_tree = tabparser.parse_to_tree(config, formatter.split)
    rb = rulebook.get_rulebook(device.hw)
    diff = patching.make_diff(current_tree, empty_tree, rb, [acl])
    patch = patching.make_patch(patching.make_pre(diff), rb, device.hw, add_comments=False)
    patch = patch.asdict()
    assert patch == {"interface ge1/1/1": OrderedDict([("undo removed", None)])}


@pytest.fixture
def multi_match_acl(device):
    # Two sibling rules both match the row "removed":
    #   re.*    -> protected, and selected as best match via higher prio
    #   removed -> deletable (no %cant_delete)
    # The resulting cant_delete must combine *both* matches, not just the selected one.
    return compile_acl_text(
        r"""
        interface %cant_delete=1
            re.* %cant_delete=1 %prio=10
            removed
        """,
        device.hw.vendor,
    )


def _make_patch(config, acl, device):
    formatter = registry_connector.get().match(device.hw).make_formatter()
    empty_tree = tabparser.parse_to_tree("", formatter.split)
    current_tree = tabparser.parse_to_tree(config, formatter.split)
    rb = rulebook.get_rulebook(device.hw)
    diff = patching.make_diff(current_tree, empty_tree, rb, [acl])
    patch = patching.make_patch(patching.make_pre(diff), rb, device.hw, add_comments=False)
    return patch.asdict()


def test_cant_delete_aggregates_across_rules(config, multi_match_acl, device):
    # The row stays deletable because at least one matching rule ("removed")
    # has no %cant_delete, even though the higher-prio selected rule ("re.*")
    # does. This is independent of generator/rule order.
    patch = _make_patch(config, multi_match_acl, device)
    assert patch == {"interface ge1/1/1": OrderedDict([("undo removed", None)])}
