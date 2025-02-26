from annet.adapters.netbox.common.query import NetboxQuery
from annet.adapters.netbox.common.storage_base import parse_glob
import pytest


def test_parse_glob():
    assert parse_glob(True, NetboxQuery(["host"])) == {"name__ie": ["host"]}
    assert parse_glob(False,NetboxQuery(["host"])) == {"name__ic": ["host."]}
    assert parse_glob(True, NetboxQuery(["site:mysite"])) == {"site": ["mysite"]}
    assert parse_glob(True, NetboxQuery(["tag:mysite", "justhost"])) == {"name__ie": ["justhost"], "tag": ["mysite"]}
    with pytest.raises(Exception):
        parse_glob(True, NetboxQuery(["host:"]))
    with pytest.raises(Exception):
        parse_glob(True, NetboxQuery(["NONONO:param"]))
