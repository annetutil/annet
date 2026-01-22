import ipaddress

import pytest

from annet.annlib.lib import LMSegment, LMSegmentList, LMSMatcher


def test_segment_cmp():
    assert LMSegment(1, 1) == LMSegment(1, 1)
    assert LMSegment(1, 4) < LMSegment(1, 2)
    assert LMSegment(1, 4) < LMSegment(2, 4)
    assert LMSegment(1, 2) < LMSegment(4, 8)


@pytest.mark.parametrize(
    "supernet, subnet",
    (
        (
            "::/0",
            "::/0",
        ),
        (
            "::/0",
            "::/1",
        ),
        (
            "2001:db8::/32",
            "2001:db8::1/128",
        ),
    ),
)
def test_segment_cmp_from_prefix(supernet, subnet):
    sup, sub = ipaddress.ip_network(supernet), ipaddress.ip_network(subnet)
    lmsup, lmsub = LMSegment.from_net(sup), LMSegment.from_net(sub)
    assert sup.version == sub.version
    assert lmsup <= lmsub


def test_matcher_empty():
    lm = LMSMatcher()
    assert lm.find("::/0") is None


def test_matcher_default():
    lm = LMSMatcher()
    lm.add("::/0")
    assert lm.find("::/0") == "::/0"
    assert lm.find("::/1") == "::/0"
    assert lm.find("2001:db8::/128") == "::/0"


def test_matcher_tree_way():
    lm = LMSMatcher()
    lm.add("::/0")
    lm.add("::/1")
    lm.add("8000::/1")
    assert lm.find("::/0") == "::/0"
    assert lm.find("1::1/128") == "::/1"
    assert lm.find("2001:db8::1/128") == "::/1"
    assert lm.find("fe80::1/128") == "8000::/1"


def test_matcher_default_fallback():
    lm = LMSMatcher()
    lm.add("::/0")
    lm.add("::/1")
    assert lm.find("2000::/16") == "::/1"
    assert lm.find("fe80::/16") == "::/0"

    lm.add("8000::/1")
    assert lm.find("fe80::/16") == "8000::/1"


def test_segment_list_add_duplicate():
    sl = LMSegmentList()
    sl.add(LMSegment(1, 2))
    sl.add(LMSegment(1, 2))
    assert len(sl.pfxs) == 1


def test_search_v4_1():
    lm = LMSMatcher()
    lm.add("10.0.0.0/8")
    lm.add("10.0.0.0/16")
    lm.add("10.0.0.0/24")

    assert lm.find("127.0.0.1") is None
    assert lm.find("10.0.0.0/32") == "10.0.0.0/24"
    assert lm.find("10.0.0.0/24") == "10.0.0.0/24"
    assert lm.find("10.0.1.0/24") == "10.0.0.0/16"


def test_search_v4_2():
    lm = LMSMatcher()
    lm.add("10.255.255.0/24")
    assert lm.find("10.255.255.176/29") == "10.255.255.0/24"

    lm.add("10.255.255.176/29")
    assert lm.find("10.255.255.176/29") == "10.255.255.176/29"
    assert lm.find("10.255.255.168/29") == "10.255.255.0/24"
    assert lm.find("10.255.255.192/29") == "10.255.255.0/24"

    lm.add("10.255.255.168/29")
    lm.add("10.255.255.192/29")

    assert lm.find("10.255.255.175/32") == "10.255.255.168/29"
    assert lm.find("10.255.255.176/32") == "10.255.255.176/29"
    assert lm.find("10.255.255.191/32") == "10.255.255.0/24"
    assert lm.find("10.255.255.192/32") == "10.255.255.192/29"
