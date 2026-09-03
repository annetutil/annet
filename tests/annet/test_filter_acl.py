import copy
import textwrap

import pytest

import annet.annlib.filter_acl
import annet.annlib.patching
from annet.rulebook.patching import compile_patching_text
from annet.vendors import registry_connector, tabparser


def test_filter_patch_preserves_patch_tree_metadata_and_empty_children():
    patch = annet.annlib.patching.PatchTree()
    patch.add("service users", {"origin": "first"}, (2, "first"))
    patch.add("service users", {"origin": "second"}, (1, "second"))
    patch.add_block("empty-block", context={"origin": "empty"}, sort_key=(3, "empty"))

    kept_children = patch.add_block("interface Ethernet1", context={"origin": "kept"}, sort_key=(4, "kept"))
    kept_children.add("description users", {"origin": "description"}, (4, "description"))
    kept_children.add("name legacy", {"origin": "name"}, (4, "name"))

    dropped_children = patch.add_block("interface Ethernet2", context={"origin": "dropped"}, sort_key=(5, "dropped"))
    dropped_children.add("name legacy", {"origin": "name"}, (5, "name"))

    original = copy.deepcopy(patch.to_json())
    acl = annet.annlib.filter_acl.make_acl("service *\nempty-block\ninterface *\n description *", "huawei")

    filtered = annet.annlib.filter_acl.filter_patch(acl, patch)

    assert patch.to_json() == original
    assert filtered is not patch
    assert [item.row for item in filtered.itms] == [
        "service users",
        "service users",
        "empty-block",
        "interface Ethernet1",
    ]
    assert [item.context for item in filtered.itms[:2]] == [{"origin": "first"}, {"origin": "second"}]
    assert [item.sort_key for item in filtered.itms[:2]] == [(2, "first"), (1, "second")]
    assert filtered.itms[0] is not patch.itms[0]
    assert filtered.itms[0].child is None
    assert filtered.itms[2].child is not None
    assert not filtered.itms[2].child
    assert filtered.itms[3].child is not None
    assert [(item.row, item.context, item.sort_key) for item in filtered.itms[3].child.itms] == [
        ("description users", {"origin": "description"}, (4, "description"))
    ]


def test_filter_patch_drops_reverse_cant_delete_parent_when_every_child_is_filtered():
    patch = annet.annlib.patching.PatchTree()
    children = patch.add_block("interface Ethernet1")
    children.add("undo description legacy", {})
    acl = annet.annlib.filter_acl.make_acl("interface *\n description * %cant_delete=1", "huawei")

    assert not annet.annlib.filter_acl.filter_patch(acl, patch)


@pytest.mark.parametrize(
    "vendor, parent, acl_text, expected",
    (
        ("huawei", "vlan 10", "vlan *\n description *", "vlan 10\n  description users\n  quit"),
        (
            "cisco",
            "interface Ethernet1",
            "interface *\n description *",
            "interface Ethernet1\n  description users\n  exit",
        ),
    ),
)
def test_filter_patch_keeps_formatter_closing_commands(vendor, parent, acl_text, expected):
    patch = annet.annlib.patching.PatchTree()
    children = patch.add_block(parent, context={}, sort_key=(0,))
    children.add("description users", {}, (0,))

    filtered = annet.annlib.filter_acl.filter_patch(
        annet.annlib.filter_acl.make_acl(acl_text, vendor),
        patch,
    )

    formatter = registry_connector.get()[vendor].make_formatter()
    assert formatter.patch(filtered) == expected


def test_filter_diff():
    """Specificity of this test: sign `+` in public-key"""

    vendor = "huawei"
    diff = textwrap.dedent("""
    - rsa peer-public-key johndoe encoding-type openssh
    -   public-key-code begin
    -     ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCvdj0k/ptPUbPMXwzPPIBqwMv1MW/xBRlf7Io+hwhV
    -     rJFIFn88Z9oHdvlvnGWO1R9VR+ZNSkncammcdhDElenqQVndLFnxav77445cLBS/AiyjBOxPv3WI6gxp
    -     +wtNcbkcJrIixDPTzOy9WRre70FKzvy1eIQK/79C7BSLtSlZgldXEnIrDolImUeMGS/c3KM= rsa-key
    -   public-key-code end
    -   foo bar
      aaa
        local-aaa-user password policy administrator
    """).strip()

    fmtr = registry_connector.get()[vendor].make_formatter()
    acl = annet.annlib.filter_acl.make_acl("rsa ~\n  foo *", vendor)

    assert (
        annet.annlib.filter_acl.filter_diff(acl, fmtr, diff)
        == textwrap.dedent("""
    - rsa peer-public-key johndoe encoding-type openssh
    -   foo bar
    """).strip()
    )


def test_ordered_and_filter_acl():
    vendor = "juniper"

    config_text = textwrap.dedent("""
      policy-options
        policy-statement SOME_POLICY
          term SOME_TERM
            from
              protocol direct
              interface lo0.0
            then
              community add SOME_COMMUNITY
              next-hop self
              accept
          term DENY
            then reject
    """).strip()
    config = tabparser.parse_to_tree(
        text=config_text,
        splitter=registry_connector.get().match(vendor).make_formatter().split,
    )

    rb_text = textwrap.dedent("""
      policy-options
        policy-statement *
          term *               %ordered
            from               %logic=annet.rulebook.common.undo_redo
              ~
            then               %logic=annet.rulebook.common.undo_redo
              community ~      %ordered
              ~
            ~                  %global
          ~                    %global
    """).strip()
    rb = {"patching": compile_patching_text(rb_text, vendor)}

    # one term is removed, it is not okay
    acl_text = textwrap.dedent("""
      policy-options
        policy-statement SOME_POLICY
          term SOME_TERM
    """).strip()
    acl = annet.annlib.filter_acl.make_acl(acl_text, vendor)

    with pytest.raises(annet.annlib.patching.AclExcludesOrderedError):
        annet.annlib.patching.apply_acl(config, acl, forbid_ordered=True, rb=rb)

    # all terms are removed, it is okay
    acl_text = textwrap.dedent("""
      policy-options
        policy-statement SOME_POLICY
          term *
    """).strip()
    acl = annet.annlib.filter_acl.make_acl(acl_text, vendor)

    # runs with no exception
    _ = annet.annlib.patching.apply_acl(config, acl, forbid_ordered=True, rb=rb)
