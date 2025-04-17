from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.tabparser import B4comFormatter
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class B4ComVendor(AbstractVendor):
    NAME = "b4com"

    def match(self) -> list[str]:
        return ["B4com"]

    @property
    def reverse(self) -> str:
        return "no"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("B4com")

    def make_formatter(self, **kwargs) -> B4comFormatter:
        return B4comFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return "exit"
