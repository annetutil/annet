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


# Real-world scenario: an ACL has both a specific rule that protects
# `diffserv domain default` via `%cant_delete` and a generic catch-all
# `diffserv domain *` without `%cant_delete`.  Aggregating cant_delete across
# *all* matching rules used to AND the two flags and drop protection from the
# `default` domain, deleting it.  Only the best matches (same %prio and same
# string_similarity) must contribute to the aggregation, so the specific rule
# wins for `default` while the generic rule still allows deleting other domains.
def test_cant_delete_specific_rule_wins_over_catch_all(device):
    acl = compile_acl_text(
        r"""
        diffserv domain default %cant_delete
        diffserv domain *
        """,
        device.hw.vendor,
    )
    config = r"""
        diffserv domain default
        diffserv domain other
    """
    patch = _make_patch(config, acl, device)
    # `default` must stay (protected by the specific rule); `other` must be deleted.
    assert patch == {"undo diffserv domain other": None}


# Regression: a reverse command like `undo shutdown` present on the device must
# stay protected by `undo shutdown %cant_delete`.  The row `undo shutdown`
# matches both the direct rule `undo shutdown %cant_delete` and the *reverse*
# form of a sibling rule `shutdown` (no %cant_delete) with the very same metric.
# Aggregating cant_delete across both best matches AND-ed the flags and dropped
# protection, so the row was wrongly deleted (emitted as `shutdown`).  Only the
# best matches sharing the selected (direct) match's direction must contribute.
@pytest.mark.parametrize(
    "acl_text",
    [
        # a single ACL with the protecting rule and a reverse-matching sibling
        r"""
        interface %cant_delete=1
            undo shutdown %cant_delete=1
            shutdown
        """,
        # sibling order must not matter
        r"""
        interface %cant_delete=1
            shutdown
            undo shutdown %cant_delete=1
        """,
        # two generators: one protects `undo shutdown`, the other emits the
        # canonical `shutdown` whose reverse form matches the same row
        r"""
        interface %cant_delete %generator_names=gen1
            undo shutdown %cant_delete=1 %generator_names=gen1
        interface %generator_names=gen2
            shutdown %generator_names=gen2
        """,
    ],
)
def test_cant_delete_protects_reverse_command(device, acl_text):
    acl = compile_acl_text(acl_text, device.hw.vendor)
    config = r"""
        interface ge1/1/1
            undo shutdown
    """
    patch = _make_patch(config, acl, device)
    # `undo shutdown` must stay; nothing may be deleted.
    assert patch == {}


def _make_patch(config, acl, device):
    formatter = registry_connector.get().match(device.hw).make_formatter()
    empty_tree = tabparser.parse_to_tree("", formatter.split)
    current_tree = tabparser.parse_to_tree(config, formatter.split)
    rb = rulebook.get_rulebook(device.hw)
    diff = patching.make_diff(current_tree, empty_tree, rb, [acl])
    patch = patching.make_patch(patching.make_pre(diff), rb, device.hw, add_comments=False)
    return patch.asdict()


@pytest.fixture
def juniper_device():
    return MockDevice("Juniper MX480", "junos 18", "jun10")


# gen1 always emits `unit *`, selected as the best match for the row "unit 0".
# gen2 emits either the same line `unit *` (merged into one rule by
# _merge_toplevel in annlib/rbparser/acl.py, %cant_delete flags concatenated)
# or the different line `unit` (kept as a separate match and combined by
# match_row_to_acl). Either way the unit must stay protected only if *every*
# matching generator asked to protect it (cant_delete AND-ed together).
@pytest.mark.parametrize("gen2_unit_line", ["unit *", "unit"])
@pytest.mark.parametrize(
    ("cant_delete_gen1", "cant_delete_gen2", "deletable"),
    [
        (0, 0, True),  # neither generator protects the unit -> deletable
        (1, 1, False),  # both generators protect the unit -> protected
        (1, 0, True),  # gen1 protects, gen2 allows -> the allowing generator wins
    ],
)
def test_cant_delete_combined_across_generators(
    juniper_device, gen2_unit_line, cant_delete_gen1, cant_delete_gen2, deletable
):
    # The (1, 0) case with the different `unit` line is the one that regressed
    # before the fix, which looked only at the cant_delete of the selected rule.
    config = r"""
        interfaces
            et-0/0/4
                unit 0
    """
    acl = compile_acl_text(
        rf"""
        interfaces %cant_delete=1 %generator_names=gen1
            * %cant_delete=1 %generator_names=gen1
                unit * %cant_delete={cant_delete_gen1} %generator_names=gen1
        interfaces %generator_names=gen2
            * %cant_delete %generator_names=gen2
                {gen2_unit_line} %cant_delete={cant_delete_gen2} %generator_names=gen2
        """,
        juniper_device.hw.vendor,
    )
    patch = _make_patch(config, acl, juniper_device)
    if deletable:
        assert patch == {"interfaces": OrderedDict([("et-0/0/4", OrderedDict([("delete unit 0", None)]))])}
    else:
        assert patch == {}
