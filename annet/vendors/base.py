import abc
import json
from typing import Any, ClassVar

from annet.annlib import jsontools
from annet.annlib.command import CommandList
from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.tabparser import CommonFormatter


class AbstractVendor(abc.ABC):
    NAME: ClassVar[str]

    @abc.abstractmethod
    def match(self) -> list[str]:
        raise NotImplementedError

    def deserialize_json_fragment(self, hw: HardwareView, text: str) -> dict[str, Any]:
        """Parse a JSON-fragment file's on-device text into the canonical dict form.

        Defaults to JSON; vendors whose config is stored differently (e.g. YAML, or a
        top-level list rather than a map) override this. ``hw`` is passed so a single
        vendor serving several device kinds can branch on hardware.
        """
        return json.loads(text)

    def serialize_json_fragment(self, hw: HardwareView, config: dict[str, Any]) -> str:
        """Render the canonical dict form back into the file's on-device text."""
        return jsontools.format_json(config)

    def apply(self, hw: HardwareView, do_commit: bool, do_finalize: bool, path: str) -> tuple[CommandList, CommandList]:
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
    def make_formatter(self, **kwargs) -> CommonFormatter:
        raise NotImplementedError
