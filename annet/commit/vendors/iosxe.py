import re
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

from .common import ensure_no_files
from .common import find_command_res

ARCHIVE_RECORD = re.compile(r"^\s*(?P<num>\d+)\s+(?P<name>\S+)(?P<recent>\s+<- Most Recent)?\s*$")


class IosXECommander(VendorCommander):
    def _show_archive(self) -> Command:
        return Command("show archive")

    def fetch(
        self,
        device: Device,  # noqa: ARG002
        files: list[str],
    ) -> DeviceCommands:
        ensure_no_files(files)
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command("show running-config"))
        res.before_cmds.add_cmd(self._show_archive())
        return res

    def _parse_commits(
        self,
        smth: DeviceResult,
    ) -> CommitState:
        """
        find show archive command and parse its output
        """
        response = find_command_res(smth, self._show_archive().cmd)
        if not response:
            return ""

        name = ""
        for line in response.out.split("\n"):
            match = ARCHIVE_RECORD.match(line)
            if not match:
                continue
            name = match.group("name")
            if match.group("recent"):
                return name
        return name  # last name

    def parse_fetch(self, smth: DeviceResult) -> DeviceConfig:
        return DeviceConfig(
            config=smth.before_cmds[0].out,
            files={},
            commit_state=self._parse_commits(smth),
        )

    def _save_config(self) -> Command:
        return Command("write memory", timeout=40)

    def apply_commit_part(
        self,
        device: Device,  # noqa: ARG002
        apply_context: object,  # noqa: ARG002
        commit_message: str,  # noqa: ARG002: unsupported
    ) -> PartCommands:
        res = PartCommands()
        res.before_cmds.add_cmd(Command("conf t"))
        res.after_cmds.add_cmd(Command("exit"))
        res.after_cmds.add_cmd(self._save_config())
        res.after_cmds.add_cmd(self._show_archive())
        return res

    def apply_commit_device(
        self,
        device: Device,  # noqa: ARG002
        commit_message: str,  # noqa: ARG002
    ) -> DeviceCommands:
        return DeviceCommands()

    def parse_commit(self, smth: DeviceResult) -> CommitState:
        return self._parse_commits(smth)

    def apply_trial_part(
        self,
        device: Device,  # noqa: ARG002
        apply_context: object,  # noqa: ARG002
        commit_message: str,  # noqa: ARG002: unsupported
        timeout: timedelta,
    ) -> PartCommands:
        res = PartCommands()
        mins = int(timeout.total_seconds() // 60) or 1
        res.before_cmds.add_cmd(Command(f"configure terminal revert timer {mins}"))
        res.after_cmds.add_cmd(Command("exit"))
        return res

    def apply_trial_device(
        self,
        device: Device,  # noqa: ARG002
        commit_message: str,  # noqa: ARG002
        timeout: timedelta,  # noqa: ARG002
    ) -> DeviceCommands:
        res = DeviceCommands()
        res.after_cmds.add_cmd(self._show_archive())
        return res

    def parse_trial(self, smth: DeviceResult) -> TrialState:
        return self._parse_commits(smth)

    def confirm_trial(
        self,
        commit_message: str,  # noqa: ARG002: unsupported
        state: TrialState,  # noqa: ARG002
    ) -> DeviceCommands:
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command("configure confirm"))
        res.after_cmds.add_cmd(self._save_config())
        res.after_cmds.add_cmd(self._show_archive())
        return res

    def parse_confirm_trial(self, smth: DeviceResult) -> CommitState:
        return self._parse_commits(smth)

    def reset_trial(
        self,
        state: TrialState,  # noqa: ARG002
    ) -> DeviceCommands:
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command("configure revert now"))
        return res

    def rollback(self, state: CommitState) -> DeviceCommands:
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command(f"configure replace {state} force", timeout=60))
        res.before_cmds.add_cmd(self._save_config())
        return res

    def quit(self) -> DeviceCommands:
        res = DeviceCommands()
        res.after_cmds.add_cmd(Command("exit", suppress_eof=True))
        return res
