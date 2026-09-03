from typing import Any

from annet.annlib.command import Command, CommandList
from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry
from annet.vendors.tabparser import AirWLCFormatter


@registry.register
class AirWLCVendor(AbstractVendor):
    NAME = "airwlc"

    def apply(
        self, hw: HardwareView, do_commit: bool, do_finalize: bool, path: str | None
    ) -> tuple[CommandList, CommandList]:
        before = CommandList(cmss=[Command("config")])
        after = CommandList(cmss=[Command("exit")])
        if do_finalize:
            after.add_cmd(Command("save config"))
        return before, after

    def match(self) -> list[str]:
        return ["Cisco.AIR.WLC"]

    @property
    def reverse(self) -> str:
        # AirOS has no universal inverse prefix. Managed rules must use custom logic.
        return "-"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("Cisco AIR-CT5520")

    def make_formatter(self, **kwargs: Any) -> AirWLCFormatter:
        return AirWLCFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return "exit"
