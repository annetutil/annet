from __future__ import annotations

from typing import Any, cast

from annet.storage import Device, Storage

from .partial import PartialGenerator


class RefGenerator(PartialGenerator):
    def __init__(self, storage: Storage, groups: list[Any] | None = None) -> None:
        super().__init__(storage)
        self.groups = groups

    def ref(self, device: Device) -> str:
        if hasattr(self, f"ref_{device.hw.vendor}"):
            return cast(str, getattr(self, f"ref_{device.hw.vendor}")(device))
        return ""

    def with_groups(self, groups: list[Any] | None) -> RefGenerator:
        return type(self)(self.storage, groups)
