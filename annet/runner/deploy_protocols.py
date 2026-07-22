from abc import abstractmethod
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from dataclasses import field
from datetime import timedelta
from typing import Any
from typing import Protocol
from typing import TypeAlias

from annet.annlib.command import CommandList
from annet.annlib.netdev.views.hardware import HardwareView
from annet.deploy import ProgressBar
from annet.storage import Device

TrialState: TypeAlias = str
CommitState: TypeAlias = str
Config: TypeAlias = str
DeviceID: TypeAlias = object


@dataclass
class DeviceConfig:
    error: str | None = None
    config: str | None = None
    files: dict[str, str] = field(default_factory=dict)
    commit_state: CommitState = ""


@dataclass
class FileCommands:
    before_cmds: CommandList = field(default_factory=CommandList)
    data: bytes = b""
    after_cmds: CommandList = field(default_factory=CommandList)


@dataclass
class DeviceCommands:
    error: str | None = None
    before_cmds: CommandList = field(default_factory=CommandList)
    upload_files: dict[str, FileCommands] = field(default_factory=dict)
    download_files: list[str] = field(default_factory=list)
    after_cmds: CommandList = field(default_factory=CommandList)

    def is_empty(self) -> bool:
        return not any(
            [
                self.before_cmds.cmss,
                self.upload_files,
                self.download_files,
                self.after_cmds.cmss,
            ]
        )


@dataclass
class PartCommands:
    before_cmds: CommandList = field(default_factory=CommandList)
    after_cmds: CommandList = field(default_factory=CommandList)


@dataclass
class CommandResult:
    cmd: str
    out: str
    error: str | None


@dataclass
class FileResult:
    before_cmds: list[CommandResult] = field(default_factory=list)
    after_cmds: list[CommandResult] = field(default_factory=list)


@dataclass
class DeviceResult:
    errors: list[Any]
    before_cmds: list[CommandResult] = field(default_factory=list)
    upload_files: dict[str, FileResult] = field(default_factory=dict)
    download_files: dict[str, bytes] = field(default_factory=dict)
    after_cmds: list[CommandResult] = field(default_factory=list)

    @property
    def all_errors(self) -> list[Any]:
        res = []
        res.extend(self.errors)
        for cmd in self.before_cmds:
            if cmd.error:
                res.append(cmd.error)
        for file_res in self.upload_files.values():
            for cmd in file_res.before_cmds:
                if cmd.error:
                    res.append(cmd.error)
            for cmd in file_res.after_cmds:
                if cmd.error:
                    res.append(cmd.error)
        for cmd in self.after_cmds:
            if cmd.error:
                res.append(cmd.error)
        return res


@dataclass
class DeployResult:
    errors: Any = None
    trial_state: TrialState | None = None
    commit_state: CommitState | None = None


class VendorCommander(Protocol):
    @abstractmethod
    def fetch(self, device: Device, files: list[str]) -> DeviceCommands:
        raise NotImplementedError

    @abstractmethod
    def parse_fetch(self, smth: DeviceResult) -> DeviceConfig:
        raise NotImplementedError

    @abstractmethod
    def apply_commit_part(self, device: Device, apply_context: object, commit_message: str) -> PartCommands:
        raise NotImplementedError

    @abstractmethod
    def apply_commit_device(self, device: Device, commit_message: str) -> DeviceCommands:
        raise NotImplementedError

    @abstractmethod
    def parse_commit(self, smth: DeviceResult) -> CommitState:
        raise NotImplementedError

    @abstractmethod
    def apply_trial_part(
        self, device: Device, apply_context: object, commit_message: str, timeout: timedelta
    ) -> PartCommands:
        raise NotImplementedError

    @abstractmethod
    def apply_trial_device(self, device: Device, commit_message: str, timeout: timedelta) -> DeviceCommands:
        raise NotImplementedError

    @abstractmethod
    def parse_trial(self, smth: DeviceResult) -> TrialState:
        raise NotImplementedError

    @abstractmethod
    def reset_trial(self, state: TrialState) -> DeviceCommands:
        raise NotImplementedError

    @abstractmethod
    def confirm_trial(self, commit_message: str, state: TrialState) -> DeviceCommands:
        raise NotImplementedError

    @abstractmethod
    def parse_confirm_trial(self, smth: DeviceResult) -> CommitState:
        raise NotImplementedError

    @abstractmethod
    def rollback(self, state: CommitState) -> DeviceCommands:
        raise NotImplementedError

    @abstractmethod
    def quit(self) -> DeviceCommands:
        raise NotImplementedError


class VendorCommanderRegistry(Protocol):
    @abstractmethod
    def match(self, hw: HardwareView) -> VendorCommander:
        raise NotImplementedError


class DeviceDriver:
    @abstractmethod
    async def execute(
        self,
        devices: list[Device],
        deploy_cmds: dict[DeviceID, DeviceCommands],
        progressbar: ProgressBar | None,
    ) -> dict[DeviceID, DeviceResult]:
        raise NotImplementedError

    @abstractmethod
    def get_connection_errors(self, devices: list[Device]) -> dict[DeviceID, str]:
        raise NotImplementedError


class DeviceDriverFactory(Protocol):
    @abstractmethod
    def make_driver(
        self, devices: list[Device], quit_commands: dict[DeviceID, DeviceCommands]
    ) -> AbstractAsyncContextManager[DeviceDriver]:
        raise NotImplementedError
