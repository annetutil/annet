from collections import OrderedDict

import pytest
from annet import rulebook
from annet.annlib.rbparser.acl import compile_acl_text

from annet import patching, tabparser
from annet.vendors import registry_connector

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
        device.hw.vendor
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
    assert patch == {
        "interface ge1/1/1": OrderedDict([("undo removed", None)])
    }
