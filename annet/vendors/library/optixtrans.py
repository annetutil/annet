from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.tabparser import OptixtransFormatter
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class OptixTransVendor(AbstractVendor):
    NAME = "optixtrans"

    def match(self) -> list[str]:
        return ["OptiXtrans"]

    @property
    def reverse(self) -> str:
        return "undo"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("Huawei OptiXtrans")

    def make_formatter(self, **kwargs) -> OptixtransFormatter:
        return OptixtransFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return "quit"
