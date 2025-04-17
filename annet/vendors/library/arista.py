from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.tabparser import AristaFormatter
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class AristaVendor(AbstractVendor):
    NAME = "arista"

    def match(self) -> list[str]:
        return ["Arista"]

    @property
    def reverse(self) -> str:
        return "no"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("Arista")

    def svi_name(self, num: int) -> str:
        return f"Vlan{num}"

    def make_formatter(self, **kwargs) -> AristaFormatter:
        return AristaFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return "exit"
