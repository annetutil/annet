"""Tests for vendor-owned (de)serialization of JSON-fragment configs.

Covers the default JSON behaviour on AbstractVendor and the NVOS YAML
list-of-single-key-maps codec on PCVendor.
"""

from collections import OrderedDict

import pytest

from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.library.pc import PCVendor, dict_to_nvos_yaml, nvos_yaml_to_dict


HW = HardwareView("PC", "")


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


def test_pc_vendor_defaults_to_json():
    vendor = PCVendor()
    text = vendor.serialize_json_fragment(HW, {"set": {"interface": {"eth0": None}}})
    # default codec is JSON, so it round-trips through the JSON deserializer
    assert vendor.deserialize_json_fragment(HW, text) == {"set": {"interface": {"eth0": None}}}
    # ...and the rendered form is JSON, not YAML
    assert text.lstrip().startswith("{")


def test_pc_vendor_uses_nvos_codec_when_matched(monkeypatch):
    vendor = PCVendor()
    monkeypatch.setattr(PCVendor, "_is_nvos", lambda self, hw: True)

    text = vendor.serialize_json_fragment(HW, NVOS_DICT)
    assert text.lstrip().startswith("- ")  # YAML list
    assert vendor.deserialize_json_fragment(HW, text) == NVOS_DICT
