import os
from collections import OrderedDict
from typing import Any, cast

import yaml

from annet.annlib.command import Command, CommandList
from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.base import AbstractVendor, is_yaml_path
from annet.vendors.registry import registry
from annet.vendors.tabparser import CommonFormatter


@registry.register
class PCVendor(AbstractVendor):
    NAME = "pc"

    def match(self) -> list[str]:
        return ["PC"]

    def _is_nvos(self, hw: HardwareView) -> bool:
        return hw.soft.startswith("nvos")

    def deserialize_json_fragment(self, hw: HardwareView, path: str, text: str) -> dict[str, Any]:
        if self._is_nvos(hw) and is_yaml_path(path):
            return nvos_yaml_to_dict(text)
        return super().deserialize_json_fragment(hw, path, text)

    def serialize_json_fragment(self, hw: HardwareView, path: str, config: dict[str, Any]) -> str:
        if self._is_nvos(hw) and is_yaml_path(path):
            return dict_to_nvos_yaml(config)
        return super().serialize_json_fragment(hw, path, config)

    @property
    def reverse(self) -> str:
        return "-"

    def apply(
        self, hw: HardwareView, do_commit: bool, do_finalize: bool, path: str | None
    ) -> tuple[CommandList, CommandList]:
        before, after = CommandList(), CommandList()

        if hw.soft.startswith(("Cumulus", "SwitchDev")):
            if os.environ.get("ETCKEEPER_CHECK", False):
                before.add_cmd(Command("etckeeper check"))

        return before, after

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("PC")

    def make_formatter(self, **kwargs: Any) -> CommonFormatter:
        return CommonFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return ""


def nvos_yaml_to_dict(text: str) -> dict[str, Any]:
    """Parse an NVOS YAML config into the canonical dict form.

    NVOS stores its config as a top-level YAML *list of single-key maps*, e.g.
    ``[{'header': {...}}, {'set': {...}}]``. The list is order-significant and the
    keys are unique, so it maps losslessly onto an ordered dict.
    """
    doc = yaml.safe_load(text)
    if doc is None:
        return OrderedDict()
    if isinstance(doc, list):
        merged: "OrderedDict[str, Any]" = OrderedDict()
        for item in doc:
            for key, value in item.items():
                merged[key] = value
        return merged
    return cast(dict[str, Any], doc)


def dict_to_nvos_yaml(config: dict[str, Any]) -> str:
    """Render the canonical dict form back into NVOS' top-level list-of-maps YAML."""
    doc = [{key: value} for key, value in config.items()]
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False)
