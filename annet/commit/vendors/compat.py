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
from .common import ensure_no_files


class UnknownBreedError(ValueError):
    def __init__(self, device: Device) -> None:
        super().__init__(f"Device(id={device.id}, hostname={device.hostname}) has an unknown breed {device.breed!r}")


# TODO: should probably get rid of breed here entirely
# this stuff is already defined in the annet.vendors
def get_config(device: Device) -> list[str]:
    if device.breed == "routeros":
        return ["/export verbose", "/user export verbose", "/file print terse detail", "/user ssh-keys print terse"]
    if device.breed.startswith(("ios", "bcom", "eltex", "nxos")):
        return ["show running-config"]
    if device.breed.startswith("jun"):
        return ["show configuration"]
    if device.breed.startswith("eos4"):
        return ["show running-config | no-more"]
    if device.breed.startswith(("h3c", "vrp")):
        return ["display current-configuration"]
    if device.breed.startswith("aruos"):
        return ["show ap-env", "show running-config no-encrypt"]
    raise UnknownBreedError(device)


class CompatCommander(VendorCommander):
    """
    Simple wrapper to call old vendor apply logic using new interface.
    """

    def fetch(self, device: Device, files: list[str]) -> DeviceCommands:
        if device.is_pc():
            return DeviceCommands(download_files=files)

        ensure_no_files(files)
        res = DeviceCommands()
        for cmd in get_config(device):
            res.before_cmds.add_cmd(Command(cmd))
        return res

    def parse_fetch(self, smth: DeviceResult) -> DeviceConfig:
        return DeviceConfig(
            config="\n".join(cmd.out for cmd in smth.before_cmds),
            files={f: out.decode() for f, out in smth.download_files.items()},
        )

    def apply_commit_part(
        self,
        device: Device,
        apply_context: object,
        commit_message: str,  # noqa: ARG002
    ) -> PartCommands:
        # currently we expect `apply_context` to be retrieved from rulebook callable
        if not callable(apply_context):
            err = "apply_context object retrieved from rulebook must be callable"
            raise TypeError(err)
        before, after = apply_context(device.hw, do_commit=True, do_finalize=True, path=None)
        return PartCommands(
            before_cmds=before,
            after_cmds=after,
        )

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
        raise TrialUnsupportedError

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
        res.after_cmds.add_cmd(Command("quit", suppress_eof=True))
        return res
