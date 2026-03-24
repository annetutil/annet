import textwrap

import pytest

import annet.annlib.filter_acl
import annet.annlib.patching
from annet.rulebook.patching import compile_patching_text
from annet.vendors import registry_connector, tabparser


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
            from               %logic=common.undo_redo
              ~
            then               %logic=common.undo_redo
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
