from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class JuniperVendor(AbstractVendor):
    NAME = "juniper"

    def match(self) -> list[str]:
        return ["Juniper"]

    @property
    def reverse(self) -> str:
        return "delete"

    def hardware(self, soft: str | None = None) -> HardwareView:
        return HardwareView("Juniper", soft)

    def svi_name(self, num: int) -> str:
        return f"irb.{num}"
