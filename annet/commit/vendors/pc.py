from datetime import timedelta

from annet.annlib.command import Command
from annet.storage import Device

from annet.runner.deploy_protocols import CommitState
from annet.runner.deploy_protocols import DeviceCommands
from annet.runner.deploy_protocols import DeviceConfig
from annet.runner.deploy_protocols import DeviceResult
from annet.runner.deploy_protocols import PartCommands
from annet.runner.deploy_protocols import TrialState
from annet.runner.deploy_protocols import VendorCommander

from .common import RollbackUnsupportedError
from .common import TrialUnsupportedError


class PCPartsUnsupportedError(ValueError):
    def __init__(self) -> None:
        super().__init__("Partial apply is unsupported on PC")


class PCCommander(VendorCommander):
    def fetch(
        self,
        device: Device,  # noqa: ARG002
        files: list[str],
    ) -> DeviceCommands:
        return DeviceCommands(download_files=files)

    def parse_fetch(self, smth: DeviceResult) -> DeviceConfig:
        return DeviceConfig(
            files={f: out.decode() for f, out in smth.download_files.items()},
        )

    def apply_commit_part(
        self,
        device: Device,  # noqa: ARG002
        apply_context: object,  # noqa: ARG002
        commit_message: str,  # noqa: ARG002
    ) -> PartCommands:
        raise PCPartsUnsupportedError

    def apply_commit_device(
        self,
        device: Device,  # noqa: ARG002
        commit_message: str,  # noqa: ARG002
    ) -> DeviceCommands:
        return DeviceCommands()

    def parse_commit(
        self,
        smth: DeviceResult,  # noqa: ARG002
    ) -> CommitState:
        return ""

    def apply_trial_part(
        self,
        device: Device,  # noqa: ARG002
        apply_context: object,  # noqa: ARG002
        commit_message: str,  # noqa: ARG002
        timeout: timedelta,  # noqa: ARG002
    ) -> PartCommands:
        raise PCPartsUnsupportedError

    def apply_trial_device(
        self,
        device: Device,  # noqa: ARG002
        commit_message: str,  # noqa: ARG002
        timeout: timedelta,  # noqa: ARG002
    ) -> DeviceCommands:
        raise TrialUnsupportedError

    def parse_trial(
        self,
        smth: DeviceResult,  # noqa: ARG002
    ) -> TrialState:
        raise TrialUnsupportedError

    def confirm_trial(
        self,
        commit_message: str,  # noqa: ARG002
        state: TrialState,  # noqa: ARG002
    ) -> DeviceCommands:
        raise TrialUnsupportedError

    def parse_confirm_trial(
        self,
        smth: DeviceResult,  # noqa: ARG002
    ) -> CommitState:
        raise TrialUnsupportedError

    def reset_trial(
        self,
        state: TrialState,  # noqa: ARG002
    ) -> DeviceCommands:
        raise TrialUnsupportedError

    def rollback(
        self,
        state: CommitState,  # noqa: ARG002
    ) -> DeviceCommands:
        raise RollbackUnsupportedError

    def quit(self) -> DeviceCommands:
        res = DeviceCommands()
        res.after_cmds.add_cmd(Command("exit", suppress_eof=True))
        return res
