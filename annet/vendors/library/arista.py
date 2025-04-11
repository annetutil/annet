from annet.annlib.netdev.views.hardware import HardwareView
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

    def hardware(self, soft: str | None = None) -> HardwareView:
        return HardwareView("Arista", soft)

    def svi_name(self, num: int) -> str:
        return f"Vlan{num}"
