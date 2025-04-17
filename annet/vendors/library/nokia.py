from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.tabparser import NokiaFormatter
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class NokiaVendor(AbstractVendor):
    NAME = "nokia"

    def match(self) -> list[str]:
        return ["Nokia"]

    @property
    def reverse(self) -> str:
        return "delete"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("Nokia")

    def make_formatter(self, **kwargs) -> NokiaFormatter:
        return NokiaFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return ""

    def diff(self, order: bool) -> str:
        return "juniper.ordered_diff" if order else "juniper.default_diff"
