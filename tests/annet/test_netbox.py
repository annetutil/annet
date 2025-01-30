from annet.adapters.netbox.v37.storage import parse_glob
import pytest


def test_parse_glob():
    assert parse_glob(["host"]) == {"name__ic": ["host"], "site": [], "tag": []}
    assert parse_glob(["site:mysite"]) == {"name__ic": [], "site": ["mysite"], "tag": []}
    assert parse_glob(["tag:mysite", "justhost"]) == {"name__ic": ["justhost"], "site": [], "tag": ["mysite"]}
    with pytest.raises(Exception):
        parse_glob(["host:"])
    with pytest.raises(Exception):
        parse_glob(["NONONO:param"])
