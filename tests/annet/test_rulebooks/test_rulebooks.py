import pytest as pytest

from annet import rulebook
from annet.vendors import registry
from tests import make_hw_stub


@pytest.fixture(params=list(registry))
def vendor(request):
    return request.param


def test_rulebooks(vendor):
    """
    Walk through every possible vendor and try to load its rulebooks
    If a rulebook has a syntax error in its template (for example %else instead of %else: as in NOCDEV-12134), the test fails
    """
    hw = make_hw_stub(vendor)
    rulebook.get_rulebook(hw)


@pytest.mark.parametrize(
    ("vendor", "rule_prefix", "expected_module", "expected_name"),
    [
        ("arista", "?/vlan ", "annet.rulebook.generic.vlandb", "simple_ranges"),
        ("cisco", "vlan %logic", "annet.rulebook.cisco.vlandb", "simple"),
        ("nexus", "vlan %logic", "annet.rulebook.generic.vlandb", "simple_no_tiny_ranges"),
        # Cisco XR resolves through the Cisco hardware/rulebook alias at runtime.
        ("iosxr", "vlan %logic", "annet.rulebook.cisco.vlandb", "simple"),
        ("asterfusioncli", "vlan * %logic", "annet.rulebook.generic.vlandb", "simple_no_tiny_ranges"),
    ],
)
def test_vlan_database_logic_has_explicit_owner(ann_connectors, vendor, rule_prefix, expected_module, expected_name):
    rb = rulebook.get_rulebook(make_hw_stub(vendor))
    matching = [rule for raw_rule, rule in rb["patching"]["local"].items() if raw_rule.startswith(rule_prefix)]

    assert len(matching) == 1
    logic = matching[0]["attrs"]["logic"]
    assert (logic.__module__, logic.__name__) == (expected_module, expected_name)
