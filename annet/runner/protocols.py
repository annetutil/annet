from abc import abstractmethod
from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from dataclasses import field
from datetime import timedelta
from enum import Enum
from typing import Protocol

from annet.deploy import ProgressBar
from annet.generators import Generators
from annet.storage import Device

from annet.runner.deploy_protocols import DeployResult
from annet.runner.deploy_protocols import DeviceCommands
from annet.runner.deploy_protocols import DeviceConfig
from annet.runner.deploy_protocols import DeviceID


class GeneratorSource(Protocol):
    @abstractmethod
    def get_generators(self, devices: list[Device]) -> dict[DeviceID, Generators]:
        raise NotImplementedError

    def get_all_generators(self) -> Generators:
        raise NotImplementedError


@dataclass
class GeneratedData:
    path: str | None
    acl: str | None
    output: str | None
    priority: int | None
    before_cmds: str | None
    after_cmds: str | None
    error: str | None
    name: str
    tags: list[str]
    aliases: list[str]
    is_json: bool = False


@dataclass
class GenerationResult:
    data: list[GeneratedData] = field(default_factory=list)
    error: str | None = None


class GeneratedDataSource(Protocol):
    @abstractmethod
    def generate(self, devices: list[Device]) -> dict[DeviceID, GenerationResult]:
        raise NotImplementedError

    @abstractmethod
    def list_files(self, devices: list[Device]) -> dict[DeviceID, list[str]]:
        raise NotImplementedError


class GeneratedDataOutput(Protocol):
    @abstractmethod
    async def print(
        self,
        devices: list[Device],
        generators_results: dict[DeviceID, GenerationResult],
        results: dict[DeviceID, DeviceConfig],
    ) -> None:
        raise NotImplementedError


class DeviceStateLoader(Protocol):
    @abstractmethod
    async def fetch(
        self,
        devices: list[Device],
        files: dict[DeviceID, list[str]],
    ) -> dict[DeviceID, DeviceConfig]:
        raise NotImplementedError


@dataclass
class FilterAcl:
    name: str
    acl: str


class FilterAclSource(Protocol):
    @abstractmethod
    def filter_acl(self, device: Device) -> list[FilterAcl]:
        raise NotImplementedError


@dataclass
class Diff:
    path: str | None
    diff: str
    error: str | None


class GeneratorMerger(Protocol):
    @abstractmethod
    def diff(
        self,
        device: Device,
        live_config: DeviceConfig,
        gen_data: Sequence[GeneratedData],
        filter_acl: list[FilterAcl],
    ) -> dict[str | None, Diff]:
        raise NotImplementedError

    @abstractmethod
    def patch(
        self,
        device: Device,
        live_config: DeviceConfig,
        gen_data: Sequence[GeneratedData],
        filter_acl: list[FilterAcl],
        commit_message: str,
    ) -> DeviceCommands:
        raise NotImplementedError

    @abstractmethod
    def patch_trial(
        self,
        device: Device,
        live_config: DeviceConfig,
        gen_data: Sequence[GeneratedData],
        filter_acl: list[FilterAcl],
        commit_message: str,
        timeout: timedelta,
    ) -> DeviceCommands:
        raise NotImplementedError

    @abstractmethod
    def make_device_config(
        self,
        device: Device,
        gen_data: Sequence[GeneratedData],
    ) -> DeviceConfig:
        raise NotImplementedError


@dataclass
class ShowGenInfo:
    name: str
    type: str
    tags: list[str]
    module: str
    description: str


@dataclass
class ShowGenDiff(Diff):
    name: str
    tags: list[str]


class DiffUI(Protocol):
    @abstractmethod
    async def show_diff(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        diff: dict[DeviceID, dict[str | None, Diff]],
        cmds: dict[DeviceID, DeviceCommands],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
        has_errors: bool,
    ) -> None:
        raise NotImplementedError


class ShowCurrentUI(Protocol):
    @abstractmethod
    def show_current(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
    ) -> None:
        raise NotImplementedError


@dataclass
class DeviceDump:
    rows: list[str]
    error: str | None


class ShowDeviceUI(Protocol):
    @abstractmethod
    def show_devices(self, devices: list[Device], data: dict[DeviceID, DeviceDump]) -> None:
        raise NotImplementedError


class TrialConfirmationAction(Enum):
    CONFIRM = "CONFIRM"
    QUIT = "QUIT"
    ROLLBACK = "ROLLBACK"


class DeployUI(Protocol):
    @abstractmethod
    def progress_bar(
        self,
        devices: list[Device],
    ) -> AbstractAsyncContextManager[ProgressBar | None]:
        raise NotImplementedError

    @abstractmethod
    def show(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        diff: dict[DeviceID, dict[str | None, Diff]],
        cmds: dict[DeviceID, DeviceCommands],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def show_errors(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        diff: dict[DeviceID, dict[str | None, Diff]],
        cmds: dict[DeviceID, DeviceCommands],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def confirm_deployment(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        diff: dict[DeviceID, dict[str | None, Diff]],
        cmds: dict[DeviceID, DeviceCommands],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def confirm_trial_confirmation(
        self,
        devices: list[Device],
        confirm_cmds: dict[DeviceID, DeviceCommands],
        rollback_cmds: dict[DeviceID, DeviceCommands],
    ) -> TrialConfirmationAction:
        raise NotImplementedError

    @abstractmethod
    def show_deploy_result(
        self,
        devices: list[Device],
        results: dict[DeviceID, DeployResult],
    ) -> None:
        raise NotImplementedError


class RollbackShowUI(Protocol):
    @abstractmethod
    def show_rollback_commands(
        self,
        devices: list[Device],
        rollback_cmds: dict[DeviceID, DeviceCommands],
    ) -> None:
        raise NotImplementedError


@dataclass
class HandlerError:
    message: str


class CommitMessageSource(Protocol):
    @abstractmethod
    async def get_message(self) -> str:
        raise NotImplementedError
