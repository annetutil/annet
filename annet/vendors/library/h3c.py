from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class H3CVendor(AbstractVendor):
    NAME = "h3c"

    def match(self) -> list[str]:
        return ["H3C"]

    @property
    def reverse(self) -> str:
        return "undo"

    def hardware(self, soft: str | None = None) -> HardwareView:
        return HardwareView("H3C", soft)
