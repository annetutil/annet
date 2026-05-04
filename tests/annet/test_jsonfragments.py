from typing import Any

import pytest

import annet.diff
from annet.annlib.jsontools import JsonFragmentAcl
from annet.annlib.netdev.views.hardware import HardwareView
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
            acl=[
                JsonFragmentAcl("/INTERFACE"),
                JsonFragmentAcl("/BREAKOUT_CFG"),
                JsonFragmentAcl("/VLAN_INTERFACE"),
            ],
            acl_safe=[
                JsonFragmentAcl("/INTERFACE/*/description"),
                JsonFragmentAcl("/VLAN_INTERFACE/*/description"),
            ],
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
    # safe diff
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
                "VLAN_INTERFACE": {  # unchanged (not in safe ACL)
                    "Ethernet0": {"vrf_name": "default"},
                    "Ethernet8": {"vrf_name": "default"},
                },
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
                "VLAN_INTERFACE": {
                    "Ethernet0": {
                        "vrf_name": "default",
                        "description": "Ether0 VLAN",
                    },  # unchanged (not in filters)
                    "Ethernet8": {"vrf_name": "default"},  # unchanged (not in ACL)
                },
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
            acl=[JsonFragmentAcl("/ACL_TABLE")],
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


def test_apply_json_fragment_cant_delete_preserves_missing_keys():
    from annet.annlib.jsontools import apply_json_fragment

    old = {"FEATURE": {"a": {"v": 1}, "b": {"v": 2}}}
    new_fragment: dict[str, Any] = {"FEATURE": {}}

    deleted = apply_json_fragment(old, new_fragment, acl=[JsonFragmentAcl("/FEATURE/*")])
    assert deleted == {"FEATURE": {}}

    preserved = apply_json_fragment(old, new_fragment, acl=[JsonFragmentAcl("/FEATURE/*", cant_delete=True)])
    assert preserved == {"FEATURE": {"a": {"v": 1}, "b": {"v": 2}}}


def test_apply_json_fragment_cant_delete_overwrites_present_keys():
    from annet.annlib.jsontools import apply_json_fragment

    old = {"FEATURE": {"a": {"v": 1}, "b": {"v": 2}}}
    new_fragment = {"FEATURE": {"a": {"v": 99}}}

    result = apply_json_fragment(old, new_fragment, acl=[JsonFragmentAcl("/FEATURE/*", cant_delete=True)])
    assert result == {"FEATURE": {"a": {"v": 99}, "b": {"v": 2}}}


def test_apply_json_fragment_mixed_cant_delete_acls():
    from annet.annlib.jsontools import apply_json_fragment

    old = {
        "PROTECTED": {"keep": 1, "also_keep": 2},
        "REGULAR": {"a": 1, "b": 2},
    }
    new_fragment: dict[str, Any] = {"PROTECTED": {}, "REGULAR": {"a": 1}}

    result = apply_json_fragment(
        old,
        new_fragment,
        acl=[
            JsonFragmentAcl("/PROTECTED/*", cant_delete=True),
            JsonFragmentAcl("/REGULAR/*"),
        ],
    )
    assert result == {
        "PROTECTED": {"keep": 1, "also_keep": 2},
        "REGULAR": {"a": 1},
    }


def _make_json_fragment_result(
    name: str,
    *,
    path: str,
    acl: list,
    config: dict,
    acl_safe: list | None = None,
) -> GeneratorJSONFragmentResult:
    return GeneratorJSONFragmentResult(
        name=name,
        tags=[name],
        path=path,
        acl=acl,
        acl_safe=acl_safe if acl_safe is not None else [],
        config=config,
        reload="reload",
        perf=GeneratorPerf(1.0, None, None),
        reload_prio=100,
    )


def test_cross_generator_cant_delete_drops_keys_no_one_emits():
    """Two generators share `/VLAN/Vlan*` with cant_delete=True; a vlan that
    nobody returns must be deleted, while keys at least one generator returned
    keep their other generators' fields intact.
    """
    path = "/etc/sonic/config_db.json"
    old_files = {
        path: {
            "VLAN": {
                "Vlan333": {"dhcpv6_servers": ["2a02:6b8::1"], "vlanid": "333"},
                "Vlan605": {"vlanid": "605"},
            }
        }
    }

    res = RunGeneratorResult()
    res.add_json_fragment(
        _make_json_fragment_result(
            "l3_tor",
            path=path,
            acl=[JsonFragmentAcl("/VLAN/Vlan*", cant_delete=True)],
            config={"VLAN": {"Vlan333": {"dhcpv6_servers": ["2a02:6b8::1"]}}},
        )
    )
    res.add_json_fragment(
        _make_json_fragment_result(
            "vlans",
            path=path,
            acl=[JsonFragmentAcl("/VLAN/Vlan*", cant_delete=True)],
            config={"VLAN": {"Vlan333": {"vlanid": "333"}}},
        )
    )

    files = res.new_json_fragment_files(old_files)
    merged, _ = files[path]
    assert merged == {
        "VLAN": {
            "Vlan333": {"dhcpv6_servers": ["2a02:6b8::1"], "vlanid": "333"},
        }
    }


def test_cross_generator_cant_delete_preserves_subtree_when_at_least_one_emits():
    """If at least one generator emits Vlan605, the other generators' missing
    sub-fields under that key are preserved (cant_delete protects the rest).
    """
    path = "/etc/sonic/config_db.json"
    old_files = {
        path: {
            "VLAN": {
                "Vlan605": {"dhcpv6_servers": ["2a02:6b8::5"], "vlanid": "605"},
            }
        }
    }

    res = RunGeneratorResult()
    res.add_json_fragment(
        _make_json_fragment_result(
            "l3_tor",
            path=path,
            acl=[JsonFragmentAcl("/VLAN/Vlan*", cant_delete=True)],
            config={"VLAN": {}},  # l3_tor doesn't return Vlan605 anymore
        )
    )
    res.add_json_fragment(
        _make_json_fragment_result(
            "vlans",
            path=path,
            acl=[JsonFragmentAcl("/VLAN/Vlan*", cant_delete=True)],
            config={"VLAN": {"Vlan605": {"vlanid": "605"}}},
        )
    )

    files = res.new_json_fragment_files(old_files)
    merged, _ = files[path]
    # Vlan605 stays; old dhcpv6_servers preserved because vlans emitted Vlan605
    # so cant_delete keeps the rest of its subtree.
    assert merged == {
        "VLAN": {
            "Vlan605": {"dhcpv6_servers": ["2a02:6b8::5"], "vlanid": "605"},
        }
    }


def test_cross_generator_cant_delete_does_not_delete_paths_owned_by_other_acl():
    """Regression: a cant_delete ACL on a broad scope must not delete keys
    that another generator's narrower ACL legitimately owns and emitted."""
    path = "/etc/sonic/config_db.json"
    old_files = {
        path: {
            "VLAN": {
                "Vlan333": {"dhcpv6_servers": ["2a02:6b8:0:3400::199"], "vlanid": "333"},
                "Vlan605": {"vlanid": "605"},
            }
        }
    }

    res = RunGeneratorResult()
    res.add_json_fragment(
        _make_json_fragment_result(
            "vlans",
            path=path,
            acl=[JsonFragmentAcl("/VLAN/Vlan*/*", cant_delete=True)],
            config={"VLAN": {"Vlan333": {"vlanid": "333"}, "Vlan605": {"vlanid": "605"}}},
        )
    )
    res.add_json_fragment(
        _make_json_fragment_result(
            "dhcp_relay",
            path=path,
            acl=[JsonFragmentAcl("/VLAN/Vlan*/dhcpv6_servers")],
            config={"VLAN": {"Vlan333": {"dhcpv6_servers": ["2a02:6b8:0:3400::199"]}}},
        )
    )

    files = res.new_json_fragment_files(old_files)
    merged, _ = files[path]
    assert merged == {
        "VLAN": {
            "Vlan333": {"dhcpv6_servers": ["2a02:6b8:0:3400::199"], "vlanid": "333"},
            "Vlan605": {"vlanid": "605"},
        }
    }


def test_cross_generator_non_cant_delete_acl_still_owns_deletion():
    """A cant_delete ACL must NOT shield a path that another generator's
    non-cant_delete ACL covers when that other generator drops it."""
    path = "/cfg.json"
    old_files = {path: {"VLAN": {"Vlan333": {"dhcpv6_servers": ["x"], "vlanid": "333"}}}}
    res = RunGeneratorResult()
    res.add_json_fragment(
        _make_json_fragment_result(
            "vlans",
            path=path,
            acl=[JsonFragmentAcl("/VLAN/Vlan*/*", cant_delete=True)],
            config={"VLAN": {"Vlan333": {"vlanid": "333"}}},
        )
    )
    res.add_json_fragment(
        _make_json_fragment_result(
            "dhcp_relay",
            path=path,
            acl=[JsonFragmentAcl("/VLAN/Vlan*/dhcpv6_servers")],
            config={"VLAN": {}},
        )
    )
    merged, _ = res.new_json_fragment_files(old_files)[path]
    assert merged == {"VLAN": {"Vlan333": {"vlanid": "333"}}}


def test_cross_generator_cant_delete_deletes_vlan_no_one_emits():
    """Vlan, который не отдал ни один генератор, должен быть удалён целиком,
    даже если cant_delete-ACL покрывает его, — потому что внутри него ничего
    не эмиттят и других ACL, владеющих этими путями, нет на верхнем уровне."""
    path = "/cfg.json"
    old_files = {
        path: {
            "VLAN": {
                "Vlan333": {"dhcpv6_servers": ["2a02:6b8::1"], "vlanid": "333"},
                "Vlan605": {"vlanid": "605"},
                "Vlan999": {"vlanid": "999"},
            }
        }
    }
    res = RunGeneratorResult()
    res.add_json_fragment(
        _make_json_fragment_result(
            "vlans",
            path=path,
            acl=[JsonFragmentAcl("/VLAN/Vlan*", cant_delete=True)],
            config={"VLAN": {"Vlan333": {"vlanid": "333"}, "Vlan605": {"vlanid": "605"}}},
        )
    )
    res.add_json_fragment(
        _make_json_fragment_result(
            "dhcp_relay",
            path=path,
            acl=[JsonFragmentAcl("/VLAN/Vlan*/dhcpv6_servers")],
            config={"VLAN": {"Vlan333": {"dhcpv6_servers": ["2a02:6b8::1"]}}},
        )
    )
    merged, _ = res.new_json_fragment_files(old_files)[path]
    assert merged == {
        "VLAN": {
            "Vlan333": {"dhcpv6_servers": ["2a02:6b8::1"], "vlanid": "333"},
            "Vlan605": {"vlanid": "605"},
        }
    }


def test_normalize_json_fragment_acl_parses_cant_delete_modifier():
    from annet.generators import _normalize_json_fragment_acl

    # `%cant_delete` → cant_delete=True
    assert _normalize_json_fragment_acl("/VLAN/Vlan* %cant_delete") == [
        JsonFragmentAcl("/VLAN/Vlan*", cant_delete=True)
    ]
    # `%cant_delete=1` → cant_delete=True
    assert _normalize_json_fragment_acl("/VLAN/Vlan* %cant_delete=1") == [
        JsonFragmentAcl("/VLAN/Vlan*", cant_delete=True)
    ]
    # `%cant_delete=0` → cant_delete=False
    assert _normalize_json_fragment_acl("/VLAN/Vlan* %cant_delete=0") == [
        JsonFragmentAcl("/VLAN/Vlan*", cant_delete=False)
    ]
    # No modifier → cant_delete=False
    assert _normalize_json_fragment_acl("/VLAN/Vlan*") == [JsonFragmentAcl("/VLAN/Vlan*")]
    # Mixed list
    assert _normalize_json_fragment_acl(["/A %cant_delete", "/B"]) == [
        JsonFragmentAcl("/A", cant_delete=True),
        JsonFragmentAcl("/B"),
    ]
