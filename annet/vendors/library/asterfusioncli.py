from typing import Any

from annet.annlib.command import Command, CommandList
from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry
from annet.vendors.tabparser import AsterfusionFormatter


@registry.register
class AsterfusionCLIVendor(AbstractVendor):
    NAME = "asterfusioncli"

    def apply(
        self, hw: HardwareView, do_commit: bool, do_finalize: bool, path: str | None
    ) -> tuple[CommandList, CommandList]:
        before, after = CommandList(), CommandList()

        before.add_cmd(Command("configure terminal"))
        after.add_cmd(Command("exit"))
        if do_finalize:
            after.add_cmd(Command("write running-config", timeout=60))

        return before, after

    def match(self) -> list[str]:
        return ["AsterfusionCLI.CX206Y"]

    @property
    def reverse(self) -> str:
        return "no"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("Asterfusion CX206Y")

    def svi_name(self, num: int) -> str:
        return f"vlan {num}"

    def make_formatter(self, **kwargs: Any) -> AsterfusionFormatter:
        return AsterfusionFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return "exit"
