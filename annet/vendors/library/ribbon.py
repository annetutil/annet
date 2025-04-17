from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.tabparser import RibbonFormatter
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class RibbonVendor(AbstractVendor):
    NAME = "ribbon"

    def match(self) -> list[str]:
        return ["Ribbon"]

    @property
    def reverse(self) -> str:
        return "delete"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("Ribbon")

    def make_formatter(self, **kwargs) -> RibbonFormatter:
        return RibbonFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return "exit"

    def diff(self, order: bool) -> str:
        return "juniper.ordered_diff" if order else "juniper.default_diff"
