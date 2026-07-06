import abc
import json
from typing import Any, ClassVar, cast

import yaml

from annet.annlib import jsontools
from annet.annlib.command import CommandList
from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.tabparser import CommonFormatter


def is_yaml_path(path: str) -> bool:
    """Whether a JSON-fragment file path denotes a YAML document by its extension."""
    return path.lower().endswith((".yaml", ".yml"))


class AbstractVendor(abc.ABC):
    NAME: ClassVar[str]

    @abc.abstractmethod
    def match(self) -> list[str]:
        raise NotImplementedError

    def deserialize_json_fragment(self, hw: HardwareView, path: str, text: str) -> dict[str, Any]:
        """Parse a JSON-fragment file's on-device text into the canonical dict form.

        Defaults to format detection by file extension: ``.yaml``/``.yml`` is parsed as
        YAML, anything else as JSON. ``hw`` and ``path`` are passed so a vendor serving
        several device kinds (or several files) can branch on hardware or file.
        """
        if is_yaml_path(path):
            return yaml.safe_load(text) or {}
        return cast("dict[str, Any]", json.loads(text))

    def serialize_json_fragment(self, hw: HardwareView, path: str, config: dict[str, Any]) -> str:
        """Render the canonical dict form back into the file's on-device text."""
        if is_yaml_path(path):
            return yaml.safe_dump(config, sort_keys=False, default_flow_style=False)
        return jsontools.format_json(config)

    def apply(
        self, hw: HardwareView, do_commit: bool, do_finalize: bool, path: str | None
    ) -> tuple[CommandList, CommandList]:
        return CommandList(), CommandList()

    @property
    @abc.abstractmethod
    def reverse(self) -> str:
        raise NotImplementedError

    def diff(self, order: bool) -> str:
        return "annet.rulebook.common.ordered_diff" if order else "annet.rulebook.common.default_diff"

    @property
    @abc.abstractmethod
    def exit(self) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def hardware(self) -> HardwareView:
        raise NotImplementedError

    def svi_name(self, num: int) -> str:
        return f"vlan{num}"

    @abc.abstractmethod
    def make_formatter(self, **kwargs: Any) -> CommonFormatter:
        raise NotImplementedError
