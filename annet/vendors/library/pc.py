from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.tabparser import CommonFormatter
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class PCVendor(AbstractVendor):
    NAME = "pc"

    def match(self) -> list[str]:
        return ["PC"]

    @property
    def reverse(self) -> str:
        return "-"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("PC")

    def make_formatter(self, **kwargs) -> CommonFormatter:
        return CommonFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return ""
