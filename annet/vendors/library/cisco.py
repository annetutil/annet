from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.tabparser import CiscoFormatter
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class CiscoVendor(AbstractVendor):
    NAME = "cisco"

    def match(self) -> list[str]:
        return ["Cisco"]

    @property
    def reverse(self) -> str:
        return "no"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("Cisco")

    def svi_name(self, num: int) -> str:
        return f"Vlan{num}"

    def make_formatter(self, **kwargs) -> CiscoFormatter:
        return CiscoFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return "exit"
