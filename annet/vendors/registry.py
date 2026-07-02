from __future__ import annotations

import enum
from collections.abc import Iterator
from operator import itemgetter
from typing import Any, overload

from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.tabparser import CommonFormatter

from .base import AbstractVendor


_SENTINEL = enum.Enum("_SENTINEL", "sentinel")
sentinel = _SENTINEL.sentinel


class GenericVendor(AbstractVendor):
    def match(self) -> list[str]:
        return []

    @property
    def reverse(self) -> str:
        return "-"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("")

    def make_formatter(self, **kwargs: Any) -> CommonFormatter:
        return CommonFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return ""


GENERIC_VENDOR = GenericVendor()


class Registry:
    def __init__(self) -> None:
        self.vendors: dict[str, AbstractVendor] = {}
        self._matchers: dict[str, AbstractVendor] = {}

    def register(self, cls: type[AbstractVendor]) -> type[AbstractVendor]:
        if not cls.NAME:
            raise RuntimeError(f"{cls.__name__} has empty NAME field")
        if cls.NAME in self.vendors:
            raise RuntimeError(f"{cls.__name__} with name {cls.NAME} already registered")
        self.vendors[cls.NAME] = cls()

        return cls

    def __add__(self, other: "Registry") -> None:
        self.vendors = dict(**other.vendors, **self.vendors)

    def __getitem__(self, item: str) -> AbstractVendor:
        if item in self.vendors:
            return self.vendors[item]
        raise RuntimeError(f"Unknown vendor {item}")

    @overload
    def match(self, hw: HardwareView | str) -> AbstractVendor: ...  # noqa: E704
    @overload
    def match(self, hw: HardwareView | str, default: _SENTINEL) -> AbstractVendor: ...  # noqa: E704

    @overload
    def match(  # noqa: E704
        self, hw: HardwareView | str, default: _SENTINEL | AbstractVendor | None
    ) -> AbstractVendor | None: ...

    def match(
        self, hw: HardwareView | str, default: _SENTINEL | AbstractVendor | None = sentinel
    ) -> AbstractVendor | None:
        if isinstance(hw, str):
            hw = HardwareView(hw, "")

        matched: list[tuple[AbstractVendor, int]] = []
        for name, vendor in self.vendors.items():
            for item in vendor.match():
                if hw.match(item):
                    matched.append((vendor, item.count(".")))

        if matched:
            return next(iter(sorted(matched, key=itemgetter(1), reverse=True)))[0]
        if default is sentinel:
            return GENERIC_VENDOR
        return default

    def get(self, item: str, default: _SENTINEL | AbstractVendor | None = sentinel) -> AbstractVendor | None:
        if item in self:
            return self[item]
        if default is sentinel:
            return GENERIC_VENDOR
        return default

    def __contains__(self, item: str) -> bool:
        return item in self.vendors

    def __iter__(self) -> Iterator[str]:
        return iter(self.vendors)


registry = Registry()
