import abc
from typing import Any

from annet.annlib.netdev.views.hardware import HardwareView, hw_to_vendor

from annet.connectors import Connector


try:
    from annet.annlib.netdev.views.hardware import vendor_to_hw
except ImportError:
    from netdev.views.hardware import vendor_to_hw


class _HardwareConnector(Connector["HarwareProvider"]):
    name = "Hardware"
    ep_name = "hardware"
    ep_by_group_only = "annet.connectors.hardware"


hardware_connector = _HardwareConnector()


class HarwareProvider(abc.ABC):
    @abc.abstractmethod
    def make_hw(self, hw_model: str, sw_version: str) -> Any:
        pass

    @abc.abstractmethod
    def vendor_to_hw(self, vendor: str) -> Any:
        pass

    @abc.abstractmethod
    def hw_to_vendor(self, hw: Any) -> str:
        pass


class AnnetHardwareProvider(HarwareProvider):
    def make_hw(self, hw_model: str, sw_version: str) -> HardwareView:
        return HardwareView(hw_model, sw_version)

    def vendor_to_hw(self, vendor: str) -> HardwareView:
        return vendor_to_hw(vendor)

    def hw_to_vendor(self, hw: HardwareView) -> str:
        return hw_to_vendor(hw)
