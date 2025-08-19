import textwrap
from collections import OrderedDict

import pytest

from annet.vendors.tabparser import parse_to_tree
from annet.vendors import registry_connector

from .. import make_hw_stub


@pytest.fixture
def juniper_config():
    return """\
version 14.1R4.10;
system {
    host-name test-juniper;
    login {
        user a {
            uid 1;
        }
        user b {
            uid 2;
        }
    }
}\
"""


@pytest.fixture
def cisco_config():
    return """\
service dhcp
ipv6 dhcp relay
interface Vlan1234
  vrf member Example
  ipv6 dhcp relay address 2001:db8:0:1200::1:101
interface Ethernet1/1/1
  speed 10000
  no shutdown
banner exec ^C
             .oooooo.   ooooo  .oooooo..o   .oooooo.     .oooooo.
            d8P'  `Y8b  `888' d8P'    `Y8  d8P'  `Y8b   d8P'  `Y8b
           888           888  Y88bo.      888          888      888
           888           888   `"Y8888o.  888          888      888
           888           888       `"Y88b 888          888      888
           `88b    ooo   888  oo     .d8P `88b    ooo  `88b    d88'
            `Y8bood8P'  o888o 8""88888P'   `Y8bood8P'   `Y8bood8P'
^C\
"""


@pytest.fixture
def nexus_config():
    return """\
service dhcp
ipv6 dhcp relay
interface Vlan1234
  vrf member Example
  ipv6 dhcp relay address 2001:db8:0:1200::1:101
interface Ethernet1/1/1
  speed 10000
  no shutdown\
"""


@pytest.fixture
def nokia_config_info():
    """Конфиг нокии полученный через configure read-only; info | no-more"""
    return textwrap.dedent("""
        card 1 {
            card-type xcm-1s
            mda 1 {
                mda-type s36-400gb-qsfpdd
                level cr4800g
            }
            fp 1 {
                egress {
                    wred-queue-control {
                        admin-state enable
                        buffer-allocation 50.0
                        reserved-cbs 99.99
                        slope-policy "WRED_FP_POLICY"
                    }
                }
                ingress {
                    network {
                        queue-policy "CORE_INGRESS"
                    }
                }
            }
        }
    """)


@pytest.fixture
def nokia_config():
    """Конфиг нокии полученный через admin show configuration | no-more"""
    return textwrap.dedent("""
        # TiMOS-B-21.2.R1 both/hops64 Nokia 7750 SR Copyright (c) 2000-2021 Nokia.
        # All rights reserved. All use subject to applicable license agreements.
        # Built on Thu Feb 25 15:50:28 PST 2021 by builder in /builds/c/212B/R1/panos/main/sros
        # Configuration format version 21.2 revision 0

        # Generated MON JUN 07 17:54:06 2021 MSK

        configure {
            card 1 {
                card-type xcm-1s
                mda 1 {
                    mda-type s36-400gb-qsfpdd
                    level cr4800g
                }
                fp 1 {
                    egress {
                        wred-queue-control {
                            admin-state enable
                            buffer-allocation 50.0
                            reserved-cbs 99.99
                            slope-policy "WRED_FP_POLICY"
                        }
                    }
                    ingress {
                        network {
                            queue-policy "CORE_INGRESS"
                        }
                    }
                }
            }
        }
        persistent-indices {
            description "Persistent indices are maintained by the system and must not be modified."
            vrtr-id {
                router-name "Example3" vrtr-id 2
                router-name "Vpn1" vrtr-id 3
            }
            vrtr-if-id {
                router-name "Base" interface-name "lag-1:1" vrtr-id 1 if-index 2
                router-name "Base" interface-name "lag-1:10" vrtr-id 1 if-index 8
                router-name "Base" interface-name "lag-2:1" vrtr-id 1 if-index 9
                router-name "Base" interface-name "lag-2:10" vrtr-id 1 if-index 10
            }
        }
        some-other-non-configure {
            description "Some text here"
        }
    """)


@pytest.fixture
def routeros_config():
    return '''\
# apr/23/2021 17:00:25 by RouterOS 6.45.7
# software id = HDTP-PUJA
#
# model = RouterBOARD 3011UiAS
# serial number = 783D00000000
/user group
set read name=read policy=local,telnet,ssh,reboot,read,test,winbox,password,web,sniff,sensitive,api,romon,tikapp,!ftp,!write,!policy,!dude skin=default
set write name=write policy=local,telnet,ssh,reboot,read,write,test,winbox,password,web,sniff,sensitive,api,romon,tikapp,!ftp,!policy,!dude skin=default
set full name=full policy=local,telnet,ssh,ftp,reboot,read,write,policy,test,winbox,password,web,sniff,sensitive,api,romon,dude,tikapp skin=default
add name=nocmon policy=read,test,api,!local,!telnet,!ssh,!ftp,!reboot,!write,!policy,!winbox,!password,!web,!sniff,!sensitive,!romon,!dude,!tikapp skin=default
/user
add address="" comment="system default user" disabled=no group=full name=admin
add address="" disabled=no group=full name=user4
add address="" disabled=no group=nocmon name=user5
/user aaa
set accounting=yes default-group=read exclude-groups="" interim-update=0s use-radius=no
/file
 0 name="skins" type="directory" creation-time=jan/01/1970 03:00:03

 1 name="auto-before-reset.backup" type="backup" size=26.6KiB creation-time=jan/02/1970 13:17:58

 2 name="pub" type="directory" creation-time=nov/27/2017 19:28:41

 3 name="user4@Example.ssh_key.txt" type=".txt file" size=606 creation-time=apr/23/2021 12:42:27 contents=ssh-dss AAAAAAAA user4@Example

 4 name="user5@example.com.ssh_key.txt" type=".txt file" size=609 creation-time=apr/23/2021 13:23:00 contents=ssh-dss AAAABBBB user5@example.com

/user ssh-keys
 0 D user=user4 bits=1024 key-owner=user4@Example
 1 D user=user5 bits=1024 key-owner=user5@example.com
    '''


@pytest.fixture
def aruba_config():
    return '''\
version 8.9.0.0-8.9.0
virtual-controller-country RU
name PUBLAB-aruba-wlc
ip-mode v4-prefer
syslog-server 10.8.8.93
syslog-level error
terminal-access
telnet-server
loginsession timeout 45
ntp-server 172.24.1.254
clock timezone UTC 00 00
rf-band 5.0

allow-new-aps


wlan access-rule user-Example
 index 4
 vlan 443
 rule any any match any any any permit

wlan access-rule Example
 index 5
 rule any any match 17 5353 5353 permit
 rule any any match any any any permit

wlan access-rule user-TmpAuth
 index 6
 vlan 441
 rule any any match any any any permit

wlan access-rule TmpAuth
 index 7
 rule any any match any any any permit

wlan access-rule Guests
 index 8
 rule any any match any any any permit

enet0-port-profile default_wired_port_profile

uplink
 preemption
 enforce none
 failover-internet-pkt-lost-cnt 10
 failover-internet-pkt-send-freq 30
 failover-vpn-timeout 180



airgroup
 disable

airgroupservice test
 disable
 id _airport._tcp
 id _rdlink._tcp

ipm
 enable


'''


@pytest.fixture
def asr_config():
    return textwrap.dedent("""\
prefix-set PFXS_Example_PRIVATENETS4-ORLONGER
  10.208.0.0/12 le 32,
  172.24.0.0/13 le 32
end-set
!
as-path-set 65401_64999
  ios-regex '_65401_64999_'
end-set
!
community-set LO_COMMUNITY
  64496:1012
end-set
!
community-set AGG_COMMUNITY
  64496:1010
end-set
!
route-policy SLBRR_EXPORT_ROUTES_RU
  set community REFLECTED_ROUTE_COMMUNITY additive
  pass
  if destination in DEFAULT_ROUTEv6_65-_127 then
    drop
  endif
  if destination in PFXS_DECAPv6 then
    done
  endif
  if destination in PFXS_Example_TUN64_ANYCASTv6-ORLONGER then
    drop
  endif
end-policy
!
router static
 address-family ipv4 unicast
  10.2.1.0/24 Null0
  10.11.6.0/22 Null0
  10.3.20.0/22 Null0
  10.8.192.0/19 Null0
  10.8.193.0/24 Null0
  10.8.199.0/24 Null0
  10.8.204.0/24 Null0
 !
 address-family ipv6 unicast
  2001:db8:e::/48 Null0
  2001:db8:f::/48 Null0
  2001:db8:20::/48 Null0
  2001:db8:21::/48 Null0
  2001:db8:22::/48 Null0
  2001:db8a::/29 Null0
 !
 vrf mgmt
  address-family ipv4 unicast
   0.0.0.0/0 5.255.226.254
   0.0.0.0/0 10.1.245.254
  !
 !
!
router isis 1
 is-type level-2-only
 net 01.01234.1001.1111.00
 log adjacency changes
 lsp-gen-interval maximum-wait 1000 initial-wait 10 secondary-wait 10
 lsp-refresh-interval 65235
 max-lsp-lifetime 65535
 min-lsp-arrivaltime maximum-wait 1000 initial-wait 10 secondary-wait 10
 address-family ipv4 unicast
  metric-style wide level 2
  advertise passive-only
  spf-interval maximum-wait 1000 initial-wait 10 secondary-wait 10
 !
 interface Loopback0
  passive
  address-family ipv4 unicast
  !
 !
 interface TenGigE0/0/2/1
  circuit-type level-2-only
  point-to-point
  lsp-interval 10
  hello-padding disable
  lsp fast-flood threshold 5
  retransmit-throttle-interval 10
  address-family ipv4 unicast
   metric 1000
   mpls ldp sync
  !
 !
!
router ospf 1
 mpls ldp sync
 maximum redistributed-prefixes 200
 max-lsa 20000
 redistribute connected metric 3000 metric-type 1
 area 0
  interface Loopback0
   passive enable
  !
  interface TenGigE0/0/2/1
   network point-to-point
  !
 !
!
router bgp 64496
 bgp router-id 10.5.123.14
 ibgp policy out enforce-modifications
 address-family ipv4 unicast
  additional-paths receive
  additional-paths send
  maximum-paths ibgp 20
  additional-paths selection route-policy ADDPATH
  redistribute connected route-policy REDISTRIBUTE_CONNECTED
  redistribute static route-policy REDISTRIBUTE_STATIC
 !
 address-family ipv6 unicast
  label mode per-vrf
  additional-paths receive
  additional-paths send
  maximum-paths ibgp 20
  additional-paths selection route-policy ADDPATH
  redistribute connected route-policy REDISTRIBUTE_CONNECTED
  redistribute static route-policy REDISTRIBUTE_STATIC
  allocate-label all
 !
""")

def test_ros_formatter_split(routeros_config):
    formatter = registry_connector.get().match(make_hw_stub("routeros")).make_formatter()
    assert formatter.split(routeros_config) == [
        '# apr/23/2021 17:00:25 by RouterOS 6.45.7',
        '# software id = HDTP-PUJA',
        '#',
        '# model = RouterBOARD 3011UiAS',
        '# serial number = 783D00000000',
        'user',
        '  group',
        '    set read name=read '
        'policy=local,telnet,ssh,reboot,read,test,winbox,password,web,sniff,sensitive,api,romon,tikapp,!ftp,!write,!policy,!dude '
        'skin=default',
        '    set write name=write '
        'policy=local,telnet,ssh,reboot,read,write,test,winbox,password,web,sniff,sensitive,api,romon,tikapp,!ftp,!policy,!dude '
        'skin=default',
        '    set full name=full '
        'policy=local,telnet,ssh,ftp,reboot,read,write,policy,test,winbox,password,web,sniff,sensitive,api,romon,dude,tikapp '
        'skin=default',
        '    add name=nocmon '
        'policy=read,test,api,!local,!telnet,!ssh,!ftp,!reboot,!write,!policy,!winbox,!password,!web,!sniff,!sensitive,!romon,!dude,!tikapp '
        'skin=default',
        'user',
        '  add address="" comment="system default user" disabled=no group=full '
        'name=admin',
        '  add address="" disabled=no group=full name=user4',
        '  add address="" disabled=no group=nocmon name=user5',
        'user',
        '  aaa',
        '    set accounting=yes default-group=read exclude-groups="" '
        'interim-update=0s use-radius=no',
        'file',
        '  print file=user4@Example.ssh_key.txt',
        '  set user4@Example.ssh_key.txt contents="ssh-dss '
        'AAAAAAAA '
        'user4@Example"',
        '  print file=user5@example.com.ssh_key.txt',
        '  set user5@example.com.ssh_key.txt contents="ssh-dss '
        'AAAABBBB '
        'user5@example.com"',
        'user',
        '  ssh-keys',
        '    import public-key-file=user4@Example.ssh_key.txt user=user4',
        '    import public-key-file=user5@example.com.ssh_key.txt user=user5'
    ]


def test_jun_formatter_split(juniper_config):
    formatter = registry_connector.get().match(make_hw_stub("juniper")).make_formatter()
    assert formatter.split(juniper_config) == [
        "version 14.1R4.10",
        "system",
        "    host-name test-juniper",
        "    login",
        "        user a",
        "            uid 1",
        "        user b",
        "            uid 2"
    ]


def test_jun_join(juniper_config):
    formatter = registry_connector.get().match(make_hw_stub("juniper")).make_formatter()
    config = parse_to_tree(juniper_config, formatter.split)
    assert formatter.join(config) == juniper_config


def test_cisco_join(cisco_config):
    formatter = registry_connector.get().match(make_hw_stub("cisco")).make_formatter()
    config = parse_to_tree(cisco_config, formatter.split)
    assert formatter.join(config) == cisco_config


def test_nexus_join(nexus_config):
    formatter = registry_connector.get().match(make_hw_stub("nexus")).make_formatter()
    config = parse_to_tree(nexus_config, formatter.split)
    assert formatter.join(config) == nexus_config


@pytest.mark.parametrize("flavor, text, config", (
    (
        # У хуавея бывают вот так странно отступлены начальные блоки
        # мы хендлим их считая что # начинает новый блок
        "huawei",
        """
  block1
    subcmd1
#
block2
  subcmd2
""",
        """
block1
  subcmd1
block2
  subcmd2
""",
    ),
    (
        # У cisco/frr может быть посередине блока
        "cisco",
        """
block
  subcmd1
! comment
  subcmd2
""",
        """
block
  subcmd1
  subcmd2
"""
    ),
))
def test_comment_block_end(flavor, text, config):
    formatter = registry_connector.get().match(make_hw_stub(flavor)).make_formatter()
    result_dict = parse_to_tree(text, formatter.split)
    result = "\n" + formatter.join(result_dict) + "\n"
    assert result == config


def test_nokia_parse_to_tree(nokia_config_info, nokia_config):
    """Конфиг нокии полученный через configure read-only; info | no-more"""
    formatter = registry_connector.get().match(make_hw_stub("nokia")).make_formatter()
    parsed = {
        "card 1": {
            "card-type xcm-1s": {},
            "mda 1": {
            "mda-type s36-400gb-qsfpdd": {},
            "level cr4800g": {}
            },
            "fp 1": {
            "egress": {
                "wred-queue-control": {
                "admin-state enable": {},
                "buffer-allocation 50.0": {},
                "reserved-cbs 99.99": {},
                "slope-policy \"WRED_FP_POLICY\"": {}
                }
            },
            "ingress": {
                "network": {
                "queue-policy \"CORE_INGRESS\"": {}
                }
            }
            }
        }
    }
    assert parse_to_tree(nokia_config, formatter.split) == parsed
    assert parse_to_tree(nokia_config_info, formatter.split) == parsed


def test_aruba_parse_to_tree(aruba_config):
    """Конфиг нокии полученный через configure read-only; info | no-more"""
    expected = {
        "version 8.9.0.0-8.9.0": {},
        "virtual-controller-country RU": {},
        "name PUBLAB-aruba-wlc": {},
        "ip-mode v4-prefer": {},
        "syslog-server 10.8.8.93": {},
        "syslog-level error": {},
        "terminal-access": {},
        "telnet-server": {},
        "loginsession timeout 45": {},
        "ntp-server 172.24.1.254": {},
        "clock timezone UTC 00 00": {},
        "rf-band 5.0": {},
        "allow-new-aps": {},
        "wlan access-rule user-Example": {
            "index 4": {},
            "vlan 443": {},
            "rule any any match any any any permit": {}
        },
        "wlan access-rule Example": {
            "index 5": {},
            "rule any any match 17 5353 5353 permit": {},
            "rule any any match any any any permit": {}
        },
        "wlan access-rule user-TmpAuth": {
            "index 6": {},
            "vlan 441": {},
            "rule any any match any any any permit": {}
        },
        "wlan access-rule TmpAuth": {
            "index 7": {},
            "rule any any match any any any permit": {}
        },
        "wlan access-rule Guests": {
            "index 8": {},
            "rule any any match any any any permit": {}
        },
        "enet0-port-profile default_wired_port_profile": {},
        "uplink": {
            "preemption": {},
            "enforce none": {},
            "failover-internet-pkt-lost-cnt 10": {},
            "failover-internet-pkt-send-freq 30": {},
            "failover-vpn-timeout 180": {}
        },
        "airgroup": {
            "disable": {}
        },
        "airgroupservice test": {
            "disable": {},
            "id _airport._tcp": {},
            "id _rdlink._tcp": {}
        },
        "ipm": {
            "enable": {}
        }
    }
    formatter = registry_connector.get().match(make_hw_stub("aruba")).make_formatter()
    parsed = parse_to_tree(aruba_config, formatter.split)
    assert parsed == expected


def test_asr_parse_to_tree(asr_config):
    expected = OrderedDict([
        (
            "prefix-set PFXS_Example_PRIVATENETS4-ORLONGER",
            OrderedDict(
                [
                    ("10.208.0.0/12 le 32,", OrderedDict()),
                    ("172.24.0.0/13 le 32", OrderedDict()),
                ]
            ),
        ),
        (
            "as-path-set 65401_64999",
            OrderedDict([("ios-regex '_65401_64999_'", OrderedDict())]),
        ),
        ("community-set LO_COMMUNITY", OrderedDict([("64496:1012", OrderedDict())])),
        ("community-set AGG_COMMUNITY", OrderedDict([("64496:1010", OrderedDict())])),
        (
            "route-policy SLBRR_EXPORT_ROUTES_RU",
            OrderedDict(
                [
                    ("set community REFLECTED_ROUTE_COMMUNITY additive", OrderedDict()),
                    ("pass", OrderedDict()),
                    (
                        "if destination in DEFAULT_ROUTEv6_65-_127 then",
                        OrderedDict([("drop", OrderedDict())]),
                    ),
                    (
                        "if destination in PFXS_DECAPv6 then",
                        OrderedDict([("done", OrderedDict())]),
                    ),
                    (
                        "if destination in PFXS_Example_TUN64_ANYCASTv6-ORLONGER then",
                        OrderedDict([("drop", OrderedDict())]),
                    ),
                ]
            ),
        ),
        (
            "router static",
            OrderedDict(
                [
                    (
                        "address-family ipv4 unicast",
                        OrderedDict(
                            [
                                ("10.2.1.0/24 Null0", OrderedDict()),
                                ("10.11.6.0/22 Null0", OrderedDict()),
                                ("10.3.20.0/22 Null0", OrderedDict()),
                                ("10.8.192.0/19 Null0", OrderedDict()),
                                ("10.8.193.0/24 Null0", OrderedDict()),
                                ("10.8.199.0/24 Null0", OrderedDict()),
                                ("10.8.204.0/24 Null0", OrderedDict()),
                            ]
                        ),
                    ),
                    (
                        "address-family ipv6 unicast",
                        OrderedDict(
                            [
                                ("2001:db8:e::/48 Null0", OrderedDict()),
                                ("2001:db8:f::/48 Null0", OrderedDict()),
                                ("2001:db8:20::/48 Null0", OrderedDict()),
                                ("2001:db8:21::/48 Null0", OrderedDict()),
                                ("2001:db8:22::/48 Null0", OrderedDict()),
                                ("2001:db8a::/29 Null0", OrderedDict()),
                            ]
                        ),
                    ),
                    (
                        "vrf mgmt",
                        OrderedDict(
                            [
                                (
                                    "address-family ipv4 unicast",
                                    OrderedDict(
                                        [
                                            ("0.0.0.0/0 5.255.226.254", OrderedDict()),
                                            (
                                                "0.0.0.0/0 10.1.245.254",
                                                OrderedDict(),
                                            ),
                                        ]
                                    ),
                                )
                            ]
                        ),
                    ),
                ]
            ),
        ),
        (
            "router isis 1",
            OrderedDict(
                [
                    ("is-type level-2-only", OrderedDict()),
                    ("net 01.01234.1001.1111.00", OrderedDict()),
                    ("log adjacency changes", OrderedDict()),
                    (
                        "lsp-gen-interval maximum-wait 1000 initial-wait 10 secondary-wait 10",
                        OrderedDict(),
                    ),
                    ("lsp-refresh-interval 65235", OrderedDict()),
                    ("max-lsp-lifetime 65535", OrderedDict()),
                    (
                        "min-lsp-arrivaltime maximum-wait 1000 initial-wait 10 secondary-wait 10",
                        OrderedDict(),
                    ),
                    (
                        "address-family ipv4 unicast",
                        OrderedDict(
                            [
                                ("metric-style wide level 2", OrderedDict()),
                                ("advertise passive-only", OrderedDict()),
                                (
                                    "spf-interval maximum-wait 1000 initial-wait 10 secondary-wait 10",
                                    OrderedDict(),
                                ),
                            ]
                        ),
                    ),
                    (
                        "interface Loopback0",
                        OrderedDict(
                            [
                                ("passive", OrderedDict()),
                                ("address-family ipv4 unicast", OrderedDict()),
                            ]
                        ),
                    ),
                    (
                        "interface TenGigE0/0/2/1",
                        OrderedDict(
                            [
                                ("circuit-type level-2-only", OrderedDict()),
                                ("point-to-point", OrderedDict()),
                                ("lsp-interval 10", OrderedDict()),
                                ("hello-padding disable", OrderedDict()),
                                ("lsp fast-flood threshold 5", OrderedDict()),
                                ("retransmit-throttle-interval 10", OrderedDict()),
                                (
                                    "address-family ipv4 unicast",
                                    OrderedDict(
                                        [
                                            ("metric 1000", OrderedDict()),
                                            ("mpls ldp sync", OrderedDict()),
                                        ]
                                    ),
                                ),
                            ]
                        ),
                    ),
                ]
            ),
        ),
        (
            "router ospf 1",
            OrderedDict(
                [
                    ("mpls ldp sync", OrderedDict()),
                    ("maximum redistributed-prefixes 200", OrderedDict()),
                    ("max-lsa 20000", OrderedDict()),
                    ("redistribute connected metric 3000 metric-type 1", OrderedDict()),
                    (
                        "area 0",
                        OrderedDict(
                            [
                                (
                                    "interface Loopback0",
                                    OrderedDict([("passive enable", OrderedDict())]),
                                ),
                                (
                                    "interface TenGigE0/0/2/1",
                                    OrderedDict(
                                        [("network point-to-point", OrderedDict())]
                                    ),
                                ),
                            ]
                        ),
                    ),
                ]
            ),
        ),
        (
            "router bgp 64496",
            OrderedDict(
                [
                    ("bgp router-id 10.5.123.14", OrderedDict()),
                    ("ibgp policy out enforce-modifications", OrderedDict()),
                    (
                        "address-family ipv4 unicast",
                        OrderedDict(
                            [
                                ("additional-paths receive", OrderedDict()),
                                ("additional-paths send", OrderedDict()),
                                ("maximum-paths ibgp 20", OrderedDict()),
                                (
                                    "additional-paths selection route-policy ADDPATH",
                                    OrderedDict(),
                                ),
                                (
                                    "redistribute connected route-policy REDISTRIBUTE_CONNECTED",
                                    OrderedDict(),
                                ),
                                (
                                    "redistribute static route-policy REDISTRIBUTE_STATIC",
                                    OrderedDict(),
                                ),
                            ]
                        ),
                    ),
                    (
                        "address-family ipv6 unicast",
                        OrderedDict(
                            [
                                ("label mode per-vrf", OrderedDict()),
                                ("additional-paths receive", OrderedDict()),
                                ("additional-paths send", OrderedDict()),
                                ("maximum-paths ibgp 20", OrderedDict()),
                                (
                                    "additional-paths selection route-policy ADDPATH",
                                    OrderedDict(),
                                ),
                                (
                                    "redistribute connected route-policy REDISTRIBUTE_CONNECTED",
                                    OrderedDict(),
                                ),
                                (
                                    "redistribute static route-policy REDISTRIBUTE_STATIC",
                                    OrderedDict(),
                                ),
                                ("allocate-label all", OrderedDict()),
                            ]
                        ),
                    ),
                ]
            ),
        ),
    ])
    formatter = registry_connector.get().match(make_hw_stub("asr")).make_formatter()
    parsed = parse_to_tree(asr_config, formatter.split)
    assert parsed == expected


def test_jun_formatter_split_whitespaces01(juniper_config):
    # sometimes juniper adds bunch of whitespaces
    # in the output of show configuration for some reason
    # here they are after the the term POLICY_0 {
    juniper_config = textwrap.dedent(r"""
    policy-options {
        policy-statement POLICY {
            term POLICY_0 {            
                then {
                    origin igp;
                    accept;
                }
            }
        }
    }
    """)
    formatter = registry_connector.get().match(make_hw_stub("juniper")).make_formatter()
    assert formatter.split(juniper_config) == [
        "policy-options",
        "    policy-statement POLICY",
        "        term POLICY_0",
        "            then",
        "                origin igp",
        "                accept",
    ]
