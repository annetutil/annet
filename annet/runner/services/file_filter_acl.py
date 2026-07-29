import sys
from pathlib import Path

from annet.storage import Device

from annet.runner.protocols import FilterAcl
from annet.runner.protocols import FilterAclSource


class FileFilterAcl(FilterAclSource):
    def __init__(self, dirname: str | Path) -> None:
        self.dirname = Path(dirname)

    def filter_acl(self, device: Device) -> list[FilterAcl]:
        file = self.dirname
        if self.dirname.is_dir():
            file = file / f"{device.hostname}.acl"

        if file.exists():
            acl_text = file.read_text(encoding="utf-8")
            return [FilterAcl(name=str(file), acl=acl_text)]
        return []


class StdinFilterAcl(FilterAclSource):
    def __init__(self) -> None:
        self.acl: str | None = None

    def filter_acl(
        self,
        device: Device,  # noqa: ARG002
    ) -> list[FilterAcl]:
        if self.acl is None:
            self.acl = sys.stdin.read()
        return [FilterAcl(name="", acl=self.acl)]


class StubFilterAcl(FilterAclSource):
    def filter_acl(
        self,
        device: Device,  # noqa: ARG002
    ) -> list[FilterAcl]:
        return []
