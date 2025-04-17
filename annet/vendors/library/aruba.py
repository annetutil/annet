from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.tabparser import ArubaFormatter
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class ArubaVendor(AbstractVendor):
    NAME = "aruba"

    def match(self) -> list[str]:
        return ["Aruba"]

    @property
    def reverse(self) -> str:
        return "no"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("Aruba")

    def make_formatter(self, **kwargs) -> ArubaFormatter:
        return ArubaFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return "exit"

    def diff(self, order: bool) -> str:
        return "common.ordered_diff" if order else "aruba.default_diff"
