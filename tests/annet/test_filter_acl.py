import textwrap

import annet.annlib.filter_acl
from annet.vendors import registry_connector


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
