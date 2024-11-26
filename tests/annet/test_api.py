from textwrap import dedent

import pytest

from annet import api


@pytest.mark.parametrize("vendors, config_text", (
    pytest.param(
        {"juniper", "ribbon"},
        """
        management-instance;
        time-zone Europe/Moscow;
        ntp {
            server 2001:db8:0:c011::1 version 2 routing-instance mgmt_junos;
            server 2001:db8:0:829::100 version 2 routing-instance mgmt_junos;
            server 2001:db8:0:829::101 version 2 routing-instance mgmt_junos;
            server 2001:db8:0:1a01::100 version 2 routing-instance mgmt_junos;
            server 2001:db8:0:1a01::101 version 2 routing-instance mgmt_junos;
            source-address 2001:db8:0:c011:0:11:c:1 routing-instance mgmt_junos;
        }
        services {
            ftp;
            ssh;
            telnet;
            netconf {
            ssh;
            }
        }
        """,
        id="juniper-ribbon"
    ),
    pytest.param(
        {"huawei", "h3c"},
        """
        port split mode mode1 slot 1
        ip vpn-instance MEth0/0/0
        ipv6-family
        ipv4-family
        ip community-filter basic DONT_ANNOUNCE_COMMUNITY index 10 permit 64496:999
        ip community-filter basic GSHUT_COMMUNITY index 10 permit 65535:0
        ntp server disable
        ntp ipv6 server disable
        ntp unicast-server ipv6 2001:db8:0:c011::1 vpn-instance MEth0/0/0
        ntp unicast-server ipv6 2001:db8:0:829::100 vpn-instance MEth0/0/0
        ntp unicast-server ipv6 2001:db8:0:829::101 vpn-instance MEth0/0/0
        ntp unicast-server ipv6 2001:db8:0:1a01::100 vpn-instance MEth0/0/0
        ntp unicast-server ipv6 2001:db8:0:1a01::101 vpn-instance MEth0/0/0
        """,
        id="huawei"
    ),
    pytest.param(
        {"arista"},
        """
        interface Ethernet2/1/1
            description region1-1d3 100ge12/0/18
            channel-group 1 mode active
            lacp rate fast
            service-profile example
        """,
        id="arista"
    ),
    pytest.param(
        # конфиги схожи
        {"cisco", "nexus", "b4com"},
        """
        interface port-channel2.3000
            encapsulation dot1q 3000
            vrf member Vpn1
            no ipv6 redirects
            ipv6 link-local fe80::6d2
            ipv6 nd suppress-ra
            ipv6 nd ra-lifetime 0
            mtu 9000
            no shutdown
        """,
        id="cisco-nexus"
    ),
    pytest.param(
        {"routeros"},
        """
        /interface vlan
        add arp=enabled arp-timeout=auto disabled=no interface=ether2 loop-protect=default loop-protect-disable-time=5m loop-protect-send-interval=5s mtu=1500 name=vlan4 use-service-tag=no vlan-id=4
        /user
        add name=user4 group=full
        /user group
        add name=nocmon
        """,
        id="routeros"
    )
))
def test_guess_hw(ann_connectors, vendors, config_text):
    config_text = dedent(config_text)
    hw, _ = api.guess_hw(config_text)
    assert hw.vendor in vendors
