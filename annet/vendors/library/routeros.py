from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class RouterOSVendor(AbstractVendor):
    NAME = "routeros"

    def match(self) -> list[str]:
        return ["RouterOS"]

    @property
    def reverse(self) -> str:
        return "remove"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("RouterOS")
