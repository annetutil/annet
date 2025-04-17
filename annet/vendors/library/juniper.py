from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.tabparser import JuniperFormatter
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

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("Juniper")

    def svi_name(self, num: int) -> str:
        return f"irb.{num}"

    def make_formatter(self, **kwargs) -> JuniperFormatter:
        return JuniperFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return ""

    def diff(self, order: bool) -> str:
        return "juniper.ordered_diff" if order else "juniper.default_diff"
