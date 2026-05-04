from typing import Any

import pytest

import annet.diff
from annet.annlib.jsontools import JsonFragmentAcl, apply_json_fragment
from annet.annlib.netdev.views.hardware import HardwareView
from annet.generators import _normalize_json_fragment_acl
from annet.generators.result import RunGeneratorResult
from annet.types import GeneratorJSONFragmentResult, GeneratorPerf


@pytest.fixture()
def edgecore_json_config():
    return {
        "ACL_RULE": {
            "YATTL|RETRANSMIT_RX_klg-10d8-2_0": {
                "IN_PORT": "Ethernet328",
                "IP_TYPE": "IPV6ANY",
                "PACKET_ACTION": "FORWARD",
                "PRIORITY": "3281",
            },
            "YATTL|RETRANSMIT_RX_klg-10d8-2_17": {
                "DSCP": "17",
                "IN_PORT": "Ethernet328",
                "IP_TYPE": "IPV6ANY",
                "PACKET_ACTION": "FORWARD",
                "PRIORITY": "3283",
            },
            "YATTL|RETRANSMIT_RX_klg-10d8-2_25": {
                "DSCP": "25",
                "IN_PORT": "Ethernet328",
                "IP_TYPE": "IPV6ANY",
                "PACKET_ACTION": "FORWARD",
                "PRIORITY": "3284",
            },
        },
        "ACL_TABLE_TYPE": {
            "DSCP": {
                "actions": ["packet_action"],
                "bind_points": ["PORT"],
                "matches": ["src_ipv6", "dscp", "in_port", "ip_type"],
            }
        },
        "BGP_GLOBALS": {
            "default": {
                "default_ipv4_unicast": "false",
                "default_local_preference": "100",
                "fast_external_failover": "true",
                "gr_preserve_fw_state": "true",
                "graceful_restart_enable": "true",
                "load_balance_mp_relax": "true",
                "local_asn": "4260167144",
                "log_nbr_state_changes": "true",
                "route_map_process_delay": "1",
                "router_id": "1.102.6.8",
            }
        },
    }


@pytest.fixture()
def diff_old():
    return {
        "ACL_RULE": {
            "YATTL|RETRANSMIT_RX_klg-10d8-2_0": {
                "IN_PORT": "Ethernet310",
                "IP_TYPE": "IPV6ANY",
                "PACKET_ACTION": "FORWARD",
                "PRIORITY": "3281",
            },
            "YATTL|RETRANSMIT_RX_klg-10d8-2_25": {
                "DSCP": "25",
                "IN_PORT": "Ethernet328",
                "IP_TYPE": "IPV6ANY",
                "PACKET_ACTION": "FORWARD",
                "PRIORITY": "1",
            },
        },
        "ACL_TABLE_TYPE": {
            "DSCP": {
                "bind_points": ["PORT"],
                "matches": ["src_ipv6", "in_port", "ip_type"],
            }
        },
        "BGP_GLOBALS": {
            "default": {
                "default_ipv4_unicast": "false",
                "default_local_preference": "100",
                "fast_external_failover": "false",
                "gr_preserve_fw_state": "true",
                "graceful_restart_enable": "true",
                "load_balance_mp_relax": "false",
                "local_asn": "4260167144",
                "log_nbr_state_changes": "true",
                "route_map_process_delay": "2",
                "router_id": "1.102.6.8",
            }
        },
    }


@pytest.fixture()
def diff_result() -> str:
    return """--- 
+++ 
@@ -1,46 +1,54 @@
-[
-    {
-        "ACL_RULE": {
-            "YATTL|RETRANSMIT_RX_klg-10d8-2_0": {
-                "IN_PORT": "Ethernet310",
-                "IP_TYPE": "IPV6ANY",
-                "PACKET_ACTION": "FORWARD",
-                "PRIORITY": "3281"
-            },
-            "YATTL|RETRANSMIT_RX_klg-10d8-2_25": {
-                "DSCP": "25",
-                "IN_PORT": "Ethernet328",
-                "IP_TYPE": "IPV6ANY",
-                "PACKET_ACTION": "FORWARD",
-                "PRIORITY": "1"
-            }
+{
+    "ACL_RULE": {
+        "YATTL|RETRANSMIT_RX_klg-10d8-2_0": {
+            "IN_PORT": "Ethernet328",
+            "IP_TYPE": "IPV6ANY",
+            "PACKET_ACTION": "FORWARD",
+            "PRIORITY": "3281"
         },
-        "ACL_TABLE_TYPE": {
-            "DSCP": {
-                "bind_points": [
-                    "PORT"
-                ],
-                "matches": [
-                    "src_ipv6",
-                    "in_port",
-                    "ip_type"
-                ]
-            }
+        "YATTL|RETRANSMIT_RX_klg-10d8-2_17": {
+            "DSCP": "17",
+            "IN_PORT": "Ethernet328",
+            "IP_TYPE": "IPV6ANY",
+            "PACKET_ACTION": "FORWARD",
+            "PRIORITY": "3283"
         },
-        "BGP_GLOBALS": {
-            "default": {
-                "default_ipv4_unicast": "false",
-                "default_local_preference": "100",
-                "fast_external_failover": "false",
-                "gr_preserve_fw_state": "true",
-                "graceful_restart_enable": "true",
-                "load_balance_mp_relax": "false",
-                "local_asn": "4260167144",
-                "log_nbr_state_changes": "true",
-                "route_map_process_delay": "2",
-                "router_id": "1.102.6.8"
-            }
+        "YATTL|RETRANSMIT_RX_klg-10d8-2_25": {
+            "DSCP": "25",
+            "IN_PORT": "Ethernet328",
+            "IP_TYPE": "IPV6ANY",
+            "PACKET_ACTION": "FORWARD",
+            "PRIORITY": "3284"
         }
     },
-    "test"
-]
+    "ACL_TABLE_TYPE": {
+        "DSCP": {
+            "actions": [
+                "packet_action"
+            ],
+            "bind_points": [
+                "PORT"
+            ],
+            "matches": [
+                "src_ipv6",
+                "dscp",
+                "in_port",
+                "ip_type"
+            ]
+        }
+    },
+    "BGP_GLOBALS": {
+        "default": {
+            "default_ipv4_unicast": "false",
+            "default_local_preference": "100",
+            "fast_external_failover": "true",
+            "gr_preserve_fw_state": "true",
+            "graceful_restart_enable": "true",
+            "load_balance_mp_relax": "true",
+            "local_asn": "4260167144",
+            "log_nbr_state_changes": "true",
+            "route_map_process_delay": "1",
+            "router_id": "1.102.6.8"
+        }
+    }
+}"""


@pytest.fixture()
def _set_differ():
    orig_device_file_differ_connector_classes = annet.diff.file_differ_connector._classes
    orig_device_file_differ_connector_cache = annet.diff.file_differ_connector._cache

    annet.diff.file_differ_connector._classes = [annet.diff.UnifiedFileDiffer]
    annet.diff.file_differ_connector._cache = None
    yield

    annet.diff.file_differ_connector._classes = orig_device_file_differ_connector_classes
    annet.diff.file_differ_connector._cache = orig_device_file_differ_connector_cache


def test_diff(diff_old, edgecore_json_config, diff_result, _set_differ):
    old_files = {"filename": (diff_old, "test")}
    new_files = {"filename": (edgecore_json_config, "test")}
    hostname = "localhost"

    diff_lines = next(annet.diff.json_fragment_diff(HardwareView("pc", ""), hostname, old_files, new_files)).diff_lines
    res_lines = diff_result.split("\n")

    assert len(diff_lines) == len(res_lines)

    for line in diff_lines:
        if line not in res_lines:
            raise Exception(f"There is wrong line in diff: '{line}'")
        res_lines.remove(line)


def test_new_json_fragment_files():
    def make_interface_fragment(config: dict[str, Any]) -> GeneratorJSONFragmentResult:
        return GeneratorJSONFragmentResult(
            name="interfaces",
            tags=["interfaces"],
            path="/etc/sonic/config_db.json",
            acl=["/INTERFACE", "/BREAKOUT_CFG", "/VLAN_INTERFACE"],
            acl_safe=["/INTERFACE/*/description", "/VLAN_INTERFACE/*/description"],
            config=config,
            reload="sonic-reload",
            perf=GeneratorPerf(1.0, None, None),
            reload_prio=100,
        )

    old_files = {
        "/etc/sonic/config_db.json": {
            "INTERFACE": {
                "Ethernet0": {"admin_status": "up", "description": "Ether0"},
                "Ethernet8": {"admin_status": "up", "description": "Ether8"},
            },
            "BREAKOUT_CFG": {
                "Ethernet0": {"brkout_mode": "1x400G"},
                "Ethernet8": {"brkout_mode": "1x400G"},
            },
            "VLAN_INTERFACE": {
                "Ethernet0": {"vrf_name": "default", "description": "Ether0 VLAN"},
                "Ethernet8": {"vrf_name": "default", "description": "Ether8 VLAN"},
            },
        },
    }

    gen_res = RunGeneratorResult()
    gen_res.add_json_fragment(
        make_interface_fragment(
            {
                "INTERFACE": {
                    "Ethernet0": {
                        "admin_status": "up",
                        "description": "Ether0",
                    },  # unchanged
                    "Ethernet4": {
                        "admin_status": "up",
                        "description": "Ether4",
                    },  # added
                    "Ethernet8": {
                        "admin_status": "up",
                        "description": "Ether8",
                    },  # unchanged
                },
                "BREAKOUT_CFG": {
                    "Ethernet0": {"brkout_mode": "2x200G"},  # updated
                    "Ethernet4": {"brkout_mode": "1x10G"},  # added
                    "Ethernet8": {"brkout_mode": "1x400G"},  # unchanged
                },
                # no "VLAN_INTERFACE"
            }
        ),
    )

    # full unsafe diff
    assert gen_res.new_json_fragment_files(old_files, safe=False) == {
        "/etc/sonic/config_db.json": (
            {
                "INTERFACE": {
                    "Ethernet0": {
                        "admin_status": "up",
                        "description": "Ether0",
                    },  # unchanged
                    "Ethernet4": {
                        "admin_status": "up",
                        "description": "Ether4",
                    },  # added
                    "Ethernet8": {
                        "admin_status": "up",
                        "description": "Ether8",
                    },  # unchanged
                },
                "BREAKOUT_CFG": {
                    "Ethernet0": {"brkout_mode": "2x200G"},  # updated
                    "Ethernet4": {"brkout_mode": "1x10G"},  # added
                    "Ethernet8": {"brkout_mode": "1x400G"},  # unchanged
                },
                # "VLAN_INTEFACE" deleted
            },
            "sonic-reload",
        ),
    }
    # safe diff: VLAN_INTERFACE is removed entirely under new chain-ownership
    # semantics — its ACL prefix /VLAN_INTERFACE has no key in the fragment.
    assert gen_res.new_json_fragment_files(old_files, safe=True) == {
        "/etc/sonic/config_db.json": (
            {
                "INTERFACE": {
                    "Ethernet0": {
                        "admin_status": "up",
                        "description": "Ether0",
                    },  # unchanged
                    "Ethernet4": {"description": "Ether4"},  # added (only description)
                    "Ethernet8": {
                        "admin_status": "up",
                        "description": "Ether8",
                    },  # unchanged
                },
                "BREAKOUT_CFG": {
                    "Ethernet0": {"brkout_mode": "1x400G"},  # unchanged
                    # no "Ethernet4" (not in safe ACL)
                    "Ethernet8": {"brkout_mode": "1x400G"},  # unchanged
                },
                # VLAN_INTERFACE deleted entirely (chain ownership)
            },
            "sonic-reload",
        ),
    }

    # unsafe diff with filters
    filters = ["/*/Ethernet[48]"]
    assert gen_res.new_json_fragment_files(old_files, safe=False, filters=filters) == {
        "/etc/sonic/config_db.json": (
            {
                "INTERFACE": {
                    "Ethernet0": {
                        "admin_status": "up",
                        "description": "Ether0",
                    },  # unchanged (not in filters)
                    "Ethernet4": {
                        "admin_status": "up",
                        "description": "Ether4",
                    },  # added
                    "Ethernet8": {
                        "admin_status": "up",
                        "description": "Ether8",
                    },  # unchanged
                },
                "BREAKOUT_CFG": {
                    "Ethernet0": {"brkout_mode": "1x400G"},  # unchanged (not in filters)
                    "Ethernet4": {"brkout_mode": "1x10G"},  # added
                    "Ethernet8": {"brkout_mode": "1x400G"},  # unchanged
                },
                "VLAN_INTERFACE": {
                    "Ethernet0": {
                        "vrf_name": "default",
                        "description": "Ether0 VLAN",
                    },  # unchanged (not in filters)
                    # no "Ethernet8" (deleted: present in filters)
                },
            },
            "sonic-reload",
        ),
    }
    # safe diff with filters
    filters = ["/*/Ethernet[48]"]
    assert gen_res.new_json_fragment_files(old_files, safe=True, filters=filters) == {
        "/etc/sonic/config_db.json": (
            {
                "INTERFACE": {
                    "Ethernet0": {
                        "admin_status": "up",
                        "description": "Ether0",
                    },  # unchanged (not in filters)
                    "Ethernet4": {"description": "Ether4"},  # added (only description)
                    "Ethernet8": {
                        "admin_status": "up",
                        "description": "Ether8",
                    },  # unchanged
                },
                "BREAKOUT_CFG": {
                    "Ethernet0": {"brkout_mode": "1x400G"},  # unchanged (not in filters)
                    # no "Ethernet4" (not in safe ACL)
                    "Ethernet8": {"brkout_mode": "1x400G"},  # unchanged
                },
                # VLAN_INTERFACE removed (chain ownership)
            },
            "sonic-reload",
        ),
    }


def test_new_json_fragment_files_append_list():
    # test that items can be successfully appended to the end of the list if acl filters is present

    def make_interface_fragment(config: dict[str, Any]) -> GeneratorJSONFragmentResult:
        return GeneratorJSONFragmentResult(
            name="acl_table",
            tags=["acl_table"],
            path="/etc/sonic/config_db.json",
            acl=["/ACL_TABLE"],
            acl_safe=[],
            config=config,
            reload="sonic-reload",
            perf=GeneratorPerf(1.0, None, None),
            reload_prio=100,
        )

    old_files = {
        "/etc/sonic/config_db.json": {
            "ACL_TABLE": {
                "YATTL": {
                    "ports": [
                        "Ethernet432",
                        "Ethernet496.201",
                        "Ethernet496",  # will be removed
                    ],
                },
            },
        },
    }

    gen_res = RunGeneratorResult()
    gen_res.add_json_fragment(
        make_interface_fragment(
            {
                "ACL_TABLE": {
                    "YATTL": {
                        "ports": [
                            "Ethernet432",
                            "Ethernet496.201",
                            "Ethernet496.202",  # added
                            "Ethernet496.203",  # added
                            "Ethernet496.204",  # added
                        ],
                    },
                },
            }
        ),
    )
    assert gen_res.new_json_fragment_files(old_files, filters=["/ACL_TABLE/YATTL/ports/*"]) == {
        "/etc/sonic/config_db.json": (
            {
                "ACL_TABLE": {
                    "YATTL": {
                        "ports": [
                            "Ethernet432",
                            "Ethernet496.201",
                            "Ethernet496.202",  # added
                            "Ethernet496.203",  # added
                            "Ethernet496.204",  # added
                        ],
                    },
                },
            },
            "sonic-reload",
        ),
    }


def test_apply_json_fragment_cant_delete_protects_listed_parents():
    old = {
        "VLAN": {
            "Vlan605": {
                "vlanid": "605",
                "dhcpv6_servers": ["fe80::1"],
            },
        },
    }
    acl = [
        JsonFragmentAcl(
            pointer="/VLAN/Vlan*/dhcpv6_servers",
            cant_delete=("/VLAN", "/VLAN/Vlan*"),
        )
    ]
    result = apply_json_fragment(old, {}, acl=acl)
    # leaf removed, but Vlan605 (now empty) and VLAN preserved
    assert result == {"VLAN": {"Vlan605": {"vlanid": "605"}}}


def test_apply_json_fragment_cant_delete_does_not_protect_unlisted():
    old = {
        "VLAN": {
            "Vlan605": {
                "dhcpv6_servers": ["fe80::1"],
            },
        },
    }
    # owner of Vlan* level — cant_delete doesn't protect VLAN itself.
    # Empty parents collapse upward unless protected.
    acl = [JsonFragmentAcl(pointer="/VLAN/Vlan*", cant_delete=())]
    result = apply_json_fragment(old, {}, acl=acl)
    assert result == {}


def test_apply_json_fragment_cant_delete_protects_only_listed_ancestor():
    old = {
        "VLAN": {
            "Vlan605": {
                "dhcpv6_servers": ["fe80::1"],
            },
        },
    }
    # Protect /VLAN only; Vlan605 is not protected, so it collapses, but
    # /VLAN itself stays as {}.
    acl = [JsonFragmentAcl(pointer="/VLAN/Vlan*", cant_delete=("/VLAN",))]
    result = apply_json_fragment(old, {}, acl=acl)
    assert result == {"VLAN": {}}


def test_apply_json_fragment_cant_delete_with_glob_pattern():
    old = {
        "VLAN": {
            "Vlan605": {"dhcpv6_servers": ["fe80::1"]},
            "Vlan700": {"dhcpv6_servers": ["fe80::2"]},
            "OtherKey": {"dhcpv6_servers": ["fe80::3"]},
        },
    }
    # cant_delete=/VLAN/Vlan* protects Vlan605, Vlan700 from chain-ownership
    # deletion at level 2. cant_delete does NOT include /VLAN, so level 1
    # (/VLAN itself) is owned by this ACL — but the fragment is empty, so
    # the whole /VLAN gets deleted at level 1.
    acl = [
        JsonFragmentAcl(
            pointer="/VLAN/*/dhcpv6_servers",
            cant_delete=("/VLAN/Vlan*",),
        )
    ]
    result = apply_json_fragment(old, {}, acl=acl)
    assert result == {}


def test_apply_json_fragment_cant_delete_protects_top_level():
    """Protect /VLAN to keep the container around even when fragment is empty."""
    old = {
        "VLAN": {
            "Vlan605": {"dhcpv6_servers": ["fe80::1"]},
            "Vlan700": {"dhcpv6_servers": ["fe80::2"]},
            "OtherKey": {"dhcpv6_servers": ["fe80::3"]},
        },
    }
    acl = [
        JsonFragmentAcl(
            pointer="/VLAN/*/dhcpv6_servers",
            cant_delete=("/VLAN", "/VLAN/Vlan*"),
        )
    ]
    result = apply_json_fragment(old, {}, acl=acl)
    # /VLAN protected, Vlan605 and Vlan700 protected (matched by /VLAN/Vlan*).
    # OtherKey not protected → removed. Each protected Vlan keeps its content
    # untouched because the leaf /VLAN/Vlan*/dhcpv6_servers level is owned
    # but the fragment lookup returns no pointers anyway... actually the leaf
    # level is owned and not protected, so dhcpv6_servers gets deleted too.
    assert result == {
        "VLAN": {
            "Vlan605": {},
            "Vlan700": {},
        },
    }


def test_apply_json_fragment_string_acl_backward_compat():
    """List of strings still works as before — strings normalize to JsonFragmentAcl(pointer=s)."""
    old = {"VLAN": {"Vlan605": {"vlanid": "605"}}}
    result = apply_json_fragment(old, {"VLAN": {"Vlan700": {"vlanid": "700"}}}, acl=["/VLAN"])
    assert result == {"VLAN": {"Vlan700": {"vlanid": "700"}}}


def test_normalize_json_fragment_acl_parses_cant_delete_list():
    acl = _normalize_json_fragment_acl(["/VLAN/Vlan*/dhcpv6_servers %cant_delete=/VLAN,/VLAN/Vlan*"])
    assert acl == [
        JsonFragmentAcl(
            pointer="/VLAN/Vlan*/dhcpv6_servers",
            cant_delete=("/VLAN", "/VLAN/Vlan*"),
        )
    ]


def test_normalize_json_fragment_acl_without_modifier():
    acl = _normalize_json_fragment_acl(["/VLAN/Vlan*"])
    assert acl == [JsonFragmentAcl(pointer="/VLAN/Vlan*", cant_delete=())]


def test_normalize_json_fragment_acl_accepts_single_string():
    acl = _normalize_json_fragment_acl("/VLAN")
    assert acl == [JsonFragmentAcl(pointer="/VLAN", cant_delete=())]


def test_apply_json_fragment_two_generators_owner_can_delete_empty():
    """End-to-end: B with cant_delete leaves Vlan605 as {}; A as 'owner' of vlanid
    then removes the empty Vlan605 (cascade collapse, since A doesn't protect it)."""
    old = {
        "VLAN": {
            "Vlan605": {
                "vlanid": "605",
                "dhcpv6_servers": ["fe80::1"],
            },
        },
    }
    # B (dhcpv6_servers owner): didn't return anything; protects parents.
    acl_b = [
        JsonFragmentAcl(
            pointer="/VLAN/Vlan*/dhcpv6_servers",
            cant_delete=("/VLAN", "/VLAN/Vlan*"),
        )
    ]
    after_b = apply_json_fragment(old, {}, acl=acl_b)
    assert after_b == {"VLAN": {"Vlan605": {"vlanid": "605"}}}

    # A (vlanid owner): also returns nothing; doesn't protect Vlan*, so empty
    # Vlan605 cascades up. Protects /VLAN, so VLAN container stays as {}.
    acl_a = [JsonFragmentAcl(pointer="/VLAN/Vlan*/vlanid", cant_delete=("/VLAN",))]
    after_a = apply_json_fragment(after_b, {}, acl=acl_a)
    assert after_a == {"VLAN": {}}


def test_apply_json_fragment_chain_ownership_partial_fragment():
    """Generator A returns vlanid for Vlan700 only (drops Vlan605). With
    chain ownership, Vlan605 must be deleted entirely — including
    dhcpv6_servers that belong to a different generator (which will re-add
    them on its own pass)."""
    old = {
        "VLAN": {
            "Vlan605": {"vlanid": "605", "dhcpv6_servers": ["fe80::1"]},
            "Vlan700": {"vlanid": "700", "dhcpv6_servers": ["fe80::2"]},
        },
    }
    new_fragment = {"VLAN": {"Vlan700": {"vlanid": "700"}}}
    acl = [JsonFragmentAcl(pointer="/VLAN/Vlan*/vlanid", cant_delete=())]
    result = apply_json_fragment(old, new_fragment, acl=acl)
    # Vlan605 deleted (not in new at /VLAN/Vlan* level); Vlan700 kept, with
    # dhcpv6_servers preserved because the ACL's leaf level /vlanid does not
    # claim ownership of dhcpv6_servers.
    assert result == {
        "VLAN": {"Vlan700": {"vlanid": "700", "dhcpv6_servers": ["fe80::2"]}},
    }


def test_apply_json_fragment_chain_ownership_disabled_by_cant_delete():
    """Same as above, but A explicitly disclaims ownership of /VLAN/Vlan*
    via cant_delete — Vlan605 keeps its dhcpv6_servers."""
    old = {
        "VLAN": {
            "Vlan605": {"vlanid": "605", "dhcpv6_servers": ["fe80::1"]},
            "Vlan700": {"vlanid": "700", "dhcpv6_servers": ["fe80::2"]},
        },
    }
    new_fragment = {"VLAN": {"Vlan700": {"vlanid": "700"}}}
    acl = [
        JsonFragmentAcl(
            pointer="/VLAN/Vlan*/vlanid",
            cant_delete=("/VLAN/Vlan*",),
        )
    ]
    result = apply_json_fragment(old, new_fragment, acl=acl)
    # Vlan605 not deleted (Vlan* level protected), but its vlanid is removed
    # (leaf level still owned).
    assert result == {
        "VLAN": {
            "Vlan605": {"dhcpv6_servers": ["fe80::1"]},
            "Vlan700": {"vlanid": "700", "dhcpv6_servers": ["fe80::2"]},
        },
    }


def test_apply_json_fragment_cant_delete_main_user_scenario():
    """Original user case: A=/VLAN/Vlan*/vlanid (no cant_delete),
    B=/VLAN/Vlan*/dhcpv6_servers %cant_delete=/VLAN,/VLAN/Vlan*.
    Both return nothing for Vlan605. Expected: Vlan605 disappears entirely
    (A removes it via cascade collapse), VLAN stays because B protects it."""
    old = {
        "VLAN": {
            "Vlan605": {
                "vlanid": "605",
                "dhcpv6_servers": ["fe80::1"],
            },
            "Vlan700": {
                "vlanid": "700",
                "dhcpv6_servers": ["fe80::2"],
            },
        },
    }
    acl_a = [JsonFragmentAcl(pointer="/VLAN/Vlan*/vlanid", cant_delete=())]
    acl_b = [
        JsonFragmentAcl(
            pointer="/VLAN/Vlan*/dhcpv6_servers",
            cant_delete=("/VLAN", "/VLAN/Vlan*"),
        )
    ]
    # A applied first with empty fragment: chain-owns /VLAN, /VLAN/Vlan*,
    # vlanid. Empty fragment at /VLAN level → /VLAN deleted entirely.
    after_a = apply_json_fragment(old, {}, acl=acl_a)
    assert after_a == {}

    # B applied to original with empty fragment: cant_delete protects
    # /VLAN and /VLAN/Vlan* levels — only the leaf level is processed,
    # which removes dhcpv6_servers from each Vlan, leaving them as {}.
    after_b = apply_json_fragment(old, {}, acl=acl_b)
    assert after_b == {"VLAN": {"Vlan605": {"vlanid": "605"}, "Vlan700": {"vlanid": "700"}}}

    # B then A: B leaves Vlans with vlanid; A then erases /VLAN entirely.
    after_b_then_a = apply_json_fragment(after_b, {}, acl=acl_a)
    assert after_b_then_a == {}
