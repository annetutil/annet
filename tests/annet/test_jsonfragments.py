import pytest
from typing import Any

import annet.diff
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
                "PRIORITY": "3281"
            },
            "YATTL|RETRANSMIT_RX_klg-10d8-2_17": {
                "DSCP": "17",
                "IN_PORT": "Ethernet328",
                "IP_TYPE": "IPV6ANY",
                "PACKET_ACTION": "FORWARD",
                "PRIORITY": "3283"
            },
            "YATTL|RETRANSMIT_RX_klg-10d8-2_25": {
                "DSCP": "25",
                "IN_PORT": "Ethernet328",
                "IP_TYPE": "IPV6ANY",
                "PACKET_ACTION": "FORWARD",
                "PRIORITY": "3284"
            },
        },
        "ACL_TABLE_TYPE": {
            "DSCP": {
                "actions": [
                    "packet_action"
                ],
                "bind_points": [
                    "PORT"
                ],
                "matches": [
                    "src_ipv6",
                    "dscp",
                    "in_port",
                    "ip_type"
                ]
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
                "router_id": "1.102.6.8"
            }
        }
    }


@pytest.fixture()
def diff_old():
    return {
        "ACL_RULE": {
            "YATTL|RETRANSMIT_RX_klg-10d8-2_0": {
                "IN_PORT": "Ethernet310",
                "IP_TYPE": "IPV6ANY",
                "PACKET_ACTION": "FORWARD",
                "PRIORITY": "3281"
            },
            "YATTL|RETRANSMIT_RX_klg-10d8-2_25": {
                "DSCP": "25",
                "IN_PORT": "Ethernet328",
                "IP_TYPE": "IPV6ANY",
                "PACKET_ACTION": "FORWARD",
                "PRIORITY": "1"
            },
        },
        "ACL_TABLE_TYPE": {
            "DSCP": {
                "bind_points": [
                    "PORT"
                ],
                "matches": [
                    "src_ipv6",
                    "in_port",
                    "ip_type"
                ]
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
                "router_id": "1.102.6.8"
            }
        }
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
        make_interface_fragment({
            "INTERFACE": {
                "Ethernet0": {"admin_status": "up", "description": "Ether0"},  # unchanged
                "Ethernet4": {"admin_status": "up", "description": "Ether4"},  # added
                "Ethernet8": {"admin_status": "up", "description": "Ether8"},  # unchanged
            },
            "BREAKOUT_CFG": {
                "Ethernet0": {"brkout_mode": "2x200G"},  # updated
                "Ethernet4": {"brkout_mode": "1x10G"},  # added
                "Ethernet8": {"brkout_mode": "1x400G"},  # unchanged
            },
            # no "VLAN_INTERFACE"
        }),
    )

    # full unsafe diff
    assert gen_res.new_json_fragment_files(old_files, safe=False) == {
        "/etc/sonic/config_db.json": (
            {
                "INTERFACE": {
                    "Ethernet0": {"admin_status": "up", "description": "Ether0"},  # unchanged
                    "Ethernet4": {"admin_status": "up", "description": "Ether4"},  # added
                    "Ethernet8": {"admin_status": "up", "description": "Ether8"},  # unchanged
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
                    "Ethernet0": {"admin_status": "up", "description": "Ether0"},  # unchanged
                    "Ethernet4": {"description": "Ether4"},  # added (only description)
                    "Ethernet8": {"admin_status": "up", "description": "Ether8"},  # unchanged
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
                    "Ethernet0": {"admin_status": "up", "description": "Ether0"},  # unchanged (not in filters)
                    "Ethernet4": {"admin_status": "up", "description": "Ether4"},  # added
                    "Ethernet8": {"admin_status": "up", "description": "Ether8"},  # unchanged
                },
                "BREAKOUT_CFG": {
                    "Ethernet0": {"brkout_mode": "1x400G"},  # unchanged (not in filters)
                    "Ethernet4": {"brkout_mode": "1x10G"},  # added
                    "Ethernet8": {"brkout_mode": "1x400G"},  # unchanged
                },
                "VLAN_INTERFACE": {
                    "Ethernet0": {"vrf_name": "default", "description": "Ether0 VLAN"},  # unchanged (not in filters)
                    # no "Ethernet8" (deleted: present in filters)
                }
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
                    "Ethernet0": {"admin_status": "up", "description": "Ether0"},  # unchanged (not in filters)
                    "Ethernet4": {"description": "Ether4"},  # added (only description)
                    "Ethernet8": {"admin_status": "up", "description": "Ether8"},  # unchanged
                },
                "BREAKOUT_CFG": {
                    "Ethernet0": {"brkout_mode": "1x400G"},  # unchanged (not in filters)
                    # no "Ethernet4" (not in safe ACL)
                    "Ethernet8": {"brkout_mode": "1x400G"},  # unchanged
                },
                "VLAN_INTERFACE": {
                    "Ethernet0": {"vrf_name": "default", "description": "Ether0 VLAN"},  # unchanged (not in filters)
                    "Ethernet8": {"vrf_name": "default"},  # unchanged (not in ACL)
                }
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
        make_interface_fragment({
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
        }),
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
