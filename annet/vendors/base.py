import abc
from typing import ClassVar

from annet.annlib.netdev.views.hardware import HardwareView


class AbstractVendor(abc.ABC):
    NAME: ClassVar[str]

    @abc.abstractmethod
    def match(self) -> list[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def reverse(self) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def hardware(self) -> HardwareView:
        raise NotImplementedError

    def svi_name(self, num: int) -> str:
        return f"vlan{num}"
