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


class IosXRCommander(VendorCommander):
    def _show_checkpoints(self) -> Command:
        return Command("show configuration commit list 1")

    def _commit_comment(self, msg: str) -> str:
        return msg.replace("\n", " ").strip()[:256]

    def fetch(
        self,
        device: Device,  # noqa: ARG002
        files: list[str],
    ) -> DeviceCommands:
        ensure_no_files(files)
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command("show running-config"))
        res.before_cmds.add_cmd(self._show_checkpoints())
        return res

    def _parse_commits(self, smth: DeviceResult) -> CommitState:
        """
        find list checkpoints command and parse its output
        """
        expected_cmd = self._show_checkpoints().cmd
        cmd_res = find_command_res(smth, expected_cmd)
        if not cmd_res:
            return ""

        for line in cmd_res.out.splitlines():
            parts = line.strip().split()
            if not parts:
                continue
            try:
                _line_no = int(parts[0])
            except ValueError:
                continue
            return parts[1]
        return ""

    def parse_fetch(self, smth: DeviceResult) -> DeviceConfig:
        return DeviceConfig(
            config=smth.before_cmds[0].out,
            files={},
            commit_state=self._parse_commits(smth),
        )

    def apply_commit_part(
        self,
        device: Device,  # noqa: ARG002
        apply_context: object,  # noqa: ARG002
        commit_message: str,
    ) -> PartCommands:
        res = PartCommands()
        res.before_cmds.add_cmd(Command("configure exclusive"))
        commit_message = self._commit_comment(commit_message)
        if commit_message:
            res.after_cmds.add_cmd(Command(f"commit show-error comment {commit_message}", timeout=90, read_timeout=90))
        else:
            res.after_cmds.add_cmd(Command("commit show-error", timeout=90, read_timeout=90))
        res.after_cmds.add_cmd(self._show_checkpoints())
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
        commit_message: str,
        timeout: timedelta,
    ) -> PartCommands:
        res = PartCommands()
        res.before_cmds.add_cmd(Command("configure exclusive"))

        secs = int(timeout.total_seconds())
        commit_message = self._commit_comment(commit_message)
        if commit_message:
            res.after_cmds.add_cmd(Command(f"commit confirmed {secs} show-error comment {commit_message}"))
        else:
            res.after_cmds.add_cmd(Command(f"commit confirmed {secs} show-error"))
        return res

    def apply_trial_device(
        self,
        device: Device,  # noqa: ARG002
        commit_message: str,  # noqa: ARG002
        timeout: timedelta,  # noqa: ARG002
    ) -> DeviceCommands:
        res = DeviceCommands()
        res.after_cmds.add_cmd(self._show_checkpoints())
        return res

    def parse_trial(self, smth: DeviceResult) -> TrialState:
        return self._parse_commits(smth)

    def confirm_trial(
        self,
        commit_message: str,
        state: TrialState,  # noqa: ARG002
    ) -> DeviceCommands:
        res = DeviceCommands()
        commit_message = self._commit_comment(commit_message)
        if commit_message:
            res.before_cmds.add_cmd(Command(f"commit comment {commit_message}"))
        else:
            res.before_cmds.add_cmd(Command("commit comment"))
        res.after_cmds.add_cmd(self._show_checkpoints())
        return res

    def parse_confirm_trial(self, smth: DeviceResult) -> CommitState:
        return self._parse_commits(smth)

    def reset_trial(self, state: TrialState) -> DeviceCommands:
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command(f"abort commit {state}"))
        return res

    def rollback(self, state: CommitState) -> DeviceCommands:
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command(f"load commit changes {state}", timeout=20))
        res.before_cmds.add_cmd(Command("commit", timeout=20))
        return res

    def quit(self) -> DeviceCommands:
        res = DeviceCommands()
        res.after_cmds.add_cmd(Command("exit", suppress_eof=True))
        return res
