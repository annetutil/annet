import pytest
from typing import Dict, Any

import annet.diff
from annet.annlib.netdev.views.hardware import HardwareView
from annet.api import _json_fragment_diff
import annet.annlib.jsontools as jsontools


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
def acl_filter1() -> str:
    return """/ACL_RULE/YATTL|RETRANSMIT_RX_klg-10d8-2_0/IN_PORT
/ACL_TABLE_TYPE"""


@pytest.fixture()
def filter1_result() -> Dict[str, Any]:
    return {
        "ACL_RULE": {
            "YATTL|RETRANSMIT_RX_klg-10d8-2_0": {
                "IN_PORT": "Ethernet328"
            }
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
        }
    }


@pytest.fixture()
def acl_filter2() -> str:
    return """
"""


@pytest.fixture()
def acl_filter3() -> str:
    return """/BGP_GLOBALS/default/default_ipv4_unicast
/BGP_GLOBALS/default/default_local_preference
/BGP_GLOBALS/123hsjd/default_local_preference"""


@pytest.fixture()
def filter3_result():
    return {
        "BGP_GLOBALS": {
            "default": {
                "default_ipv4_unicast": "false",
                "default_local_preference": "100"
            }
        }
    }


@pytest.fixture()
def acl_filter4() -> str:
    return """/ACL_*LE/*/I*"""


@pytest.fixture()
def filter4_result() -> Dict[str, Any]:
    return {
        "ACL_RULE": {
            "YATTL|RETRANSMIT_RX_klg-10d8-2_0": {
                "IN_PORT": "Ethernet328",
                "IP_TYPE": "IPV6ANY",
            },
            "YATTL|RETRANSMIT_RX_klg-10d8-2_17": {
                "IN_PORT": "Ethernet328",
                "IP_TYPE": "IPV6ANY",
            },
            "YATTL|RETRANSMIT_RX_klg-10d8-2_25": {
                "IN_PORT": "Ethernet328",
                "IP_TYPE": "IPV6ANY",
            },
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


def test_acl_filter_correct_parts(edgecore_json_config, acl_filter1, filter1_result):
    filters = acl_filter1.split("\n")
    result = jsontools.apply_acl_filters(edgecore_json_config, filters)

    assert result == filter1_result


def test_acl_filter_empty_line(edgecore_json_config, acl_filter2):
    filters = acl_filter2.split("\n")
    result = jsontools.apply_acl_filters(edgecore_json_config, filters)

    assert result == {}


def test_acl_filter_wrong_filters_skip(edgecore_json_config, acl_filter3, filter3_result):
    filters = acl_filter3.split("\n")
    result = jsontools.apply_acl_filters(edgecore_json_config, filters)

    assert result == filter3_result


def test_acl_filter_wildcards(edgecore_json_config, acl_filter4, filter4_result):
    filters = acl_filter4.split("\n")
    result = jsontools.apply_acl_filters(edgecore_json_config, filters)

    assert result == filter4_result


@pytest.fixture()
def _set_differ():
    orig_device_file_differ_connector_classes = annet.diff.file_differ_connector._classes
    orig_device_file_differ_connector_cache = annet.diff.file_differ_connector._cache

    annet.diff.file_differ_connector._classes = [annet.diff.PrintableDeviceDiffer]
    annet.diff.file_differ_connector._cache = None
    yield

    annet.diff.file_differ_connector._classes = orig_device_file_differ_connector_classes
    annet.diff.file_differ_connector._cache = orig_device_file_differ_connector_cache

def test_diff(diff_old, edgecore_json_config, diff_result, _set_differ):
    old_files = {"filename": (diff_old, "test")}
    new_files = {"filename": (edgecore_json_config, "test")}
    hostname = "localhost"

    diff_lines = next(_json_fragment_diff(HardwareView("pc", ""), hostname, old_files, new_files)).diff_lines
    res_lines = diff_result.split("\n")

    assert len(diff_lines) == len(res_lines)

    for line in diff_lines:
        if line not in res_lines:
            raise Exception(f"There is wrong line in diff: '{line}'")
        res_lines.remove(line)
