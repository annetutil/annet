import abc
from typing import ClassVar

from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.tabparser import CommonFormatter


class AbstractVendor(abc.ABC):
    NAME: ClassVar[str]

    @abc.abstractmethod
    def match(self) -> list[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def reverse(self) -> str:
        raise NotImplementedError

    def diff(self, order: bool) -> str:
        return "common.ordered_diff" if order else "common.default_diff"

    @property
    @abc.abstractmethod
    def exit(self) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def hardware(self) -> HardwareView:
        raise NotImplementedError

    def svi_name(self, num: int) -> str:
        return f"vlan{num}"

    @abc.abstractmethod
    def make_formatter(self, **kwargs) -> CommonFormatter:
        raise NotImplementedError
