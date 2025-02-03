from annet.adapters.netbox.v37.storage import parse_glob
import pytest


def test_parse_glob():
    assert parse_glob(True, ["host"]) == {"name__ie": ["host"]}
    assert parse_glob(False, ["host"]) == {"name__ic": ["host."]}
    assert parse_glob(True, ["site:mysite"]) == {"site": ["mysite"]}
    assert parse_glob(True, ["tag:mysite", "justhost"]) == {"name__ie": ["justhost"], "tag": ["mysite"]}
    with pytest.raises(Exception):
        parse_glob(True, ["host:"])
    with pytest.raises(Exception):
        parse_glob(True, ["NONONO:param"])
