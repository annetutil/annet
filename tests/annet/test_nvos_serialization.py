"""Tests for vendor-owned (de)serialization of JSON-fragment configs.

Covers the default JSON behaviour on AbstractVendor and the NVOS YAML
list-of-single-key-maps codec on PCVendor.
"""

from collections import OrderedDict

from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.library.pc import PCVendor, dict_to_nvos_yaml, nvos_yaml_to_dict


HW = HardwareView("PC", "")
NVOS_HW = HardwareView("PC", "nvos")


# Example NVOS config: top-level YAML list of single-key maps.
NVOS_YAML = """\
- header:
    model: q3400
    nvue-api-version: nvue_v1
    rev-id: 1.0
    version: 3.2.0.0
- set:
    interface:
      eth0:
"""

NVOS_DICT = {
    "header": {
        "model": "q3400",
        "nvue-api-version": "nvue_v1",
        "rev-id": 1.0,
        "version": "3.2.0.0",
    },
    "set": {"interface": {"eth0": None}},
}


def test_nvos_yaml_to_dict_collapses_top_level_list():
    result = nvos_yaml_to_dict(NVOS_YAML)
    assert result == NVOS_DICT
    # order of the top-level list is preserved as dict insertion order
    assert list(result.keys()) == ["header", "set"]


def test_nvos_yaml_to_dict_empty():
    assert nvos_yaml_to_dict("") == OrderedDict()


def test_dict_to_nvos_yaml_emits_top_level_list():
    text = dict_to_nvos_yaml(NVOS_DICT)
    # top level must be a YAML list, not a map
    assert text.lstrip().startswith("- ")


def test_nvos_round_trip_preserves_content_and_order():
    cfg = OrderedDict(NVOS_DICT)
    restored = nvos_yaml_to_dict(dict_to_nvos_yaml(cfg))
    assert restored == cfg
    assert list(restored.keys()) == list(cfg.keys())


def test_json_path_uses_json_codec():
    vendor = PCVendor()
    cfg = {"set": {"interface": {"eth0": None}}}
    text = vendor.serialize_json_fragment(HW, "config.json", cfg)
    assert text.lstrip().startswith("{")  # JSON, not YAML
    assert vendor.deserialize_json_fragment(HW, "config.json", text) == cfg


def test_yaml_path_non_nvos_uses_plain_yaml():
    vendor = PCVendor()
    cfg = {"set": {"interface": {"eth0": None}}}
    text = vendor.serialize_json_fragment(HW, "config.yaml", cfg)
    # plain YAML mapping at the top level, NOT the NVOS list-of-maps form
    assert not text.lstrip().startswith("- ")
    assert vendor.deserialize_json_fragment(HW, "config.yaml", text) == cfg


def test_nvos_yaml_path_uses_nvos_codec():
    vendor = PCVendor()
    text = vendor.serialize_json_fragment(NVOS_HW, "startup.yaml", NVOS_DICT)
    assert text.lstrip().startswith("- ")  # NVOS top-level list of maps
    assert vendor.deserialize_json_fragment(NVOS_HW, "startup.yaml", text) == NVOS_DICT


def test_nvos_json_path_still_uses_json_codec():
    # NVOS only changes YAML handling; a .json file on an NVOS box is still JSON.
    vendor = PCVendor()
    cfg = {"set": {"interface": {"eth0": None}}}
    text = vendor.serialize_json_fragment(NVOS_HW, "config.json", cfg)
    assert text.lstrip().startswith("{")
    assert vendor.deserialize_json_fragment(NVOS_HW, "config.json", text) == cfg
