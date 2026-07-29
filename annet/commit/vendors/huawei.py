import re
from datetime import timedelta
from uuid import uuid4

from annet.annlib.command import Command
from annet.annlib.command import Question
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

INVALID_LABEL_SYMBOLS = re.compile(r"[^a-zA-Z0-9@.,:;\-_+=\[\](){}]+")


class HuaweiCommander(VendorCommander):
    def _show_checkpoints(self) -> Command:
        return Command("display configuration commit list | no-more")

    def _commit_label(self, msg: str) -> str:
        msg = INVALID_LABEL_SYMBOLS.sub("_", msg).strip("_")[:200]
        if not msg:
            return ""
        if msg[0].isnumeric():
            msg = "_" + msg
        return f"{msg}-{uuid4()}"

    def fetch(
        self,
        device: Device,  # noqa: ARG002
        files: list[str],
    ) -> DeviceCommands:
        ensure_no_files(files)
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command("display current-configuration"))
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
        for line in cmd_res.out.split("\n"):
            parts = line.split()
            if parts and parts[0].isnumeric():
                return parts[1]
        return ""

    def parse_fetch(self, smth: DeviceResult) -> DeviceConfig:
        return DeviceConfig(
            config=smth.before_cmds[0].out,
            files={},
            commit_state=self._parse_commits(smth),
        )

    def _return(self) -> Command:
        return Command("return")

    def apply_commit_part(
        self,
        device: Device,  # noqa: ARG002
        apply_context: object,  # noqa: ARG002
        commit_message: str,
    ) -> PartCommands:
        res = PartCommands()
        res.before_cmds.add_cmd(Command("system"))

        confirm = [Question("The trial configuration will be confirmed. Continue?", "Y")]
        commit_message = self._commit_label(commit_message)
        if commit_message:
            res.after_cmds.add_cmd(Command(f"commit label {commit_message}", questions=confirm))
        else:
            res.after_cmds.add_cmd(Command("commit", questions=confirm))
        res.after_cmds.add_cmd(self._return())
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
        commit_message: str,  # noqa: ARG002
        timeout: timedelta,
    ) -> PartCommands:
        res = PartCommands()
        res.before_cmds.add_cmd(Command("system"))

        persist_id = f"ann-{uuid4()}"
        seconds = int(timeout.total_seconds())
        res.after_cmds.add_cmd(Command(f"commit trial {seconds} persist {persist_id}"))
        res.after_cmds.add_cmd(self._return())
        return res

    def apply_trial_device(
        self,
        device: Device,  # noqa: ARG002
        commit_message: str,  # noqa: ARG002
        timeout: timedelta,  # noqa: ARG002
    ) -> DeviceCommands:
        return DeviceCommands()

    def parse_trial(self, smth: DeviceResult) -> TrialState:
        cmd_res = find_command_res(smth, "commit trial ", exact=False)
        if not cmd_res:
            return ""
        return cmd_res.cmd.rsplit(" ", maxsplit=1)[1]

    def confirm_trial(self, commit_message: str, state: TrialState) -> DeviceCommands:
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command("system"))
        confirm = [Question("The trial configuration will be confirmed. Continue?", "Y")]
        res.before_cmds.add_cmd(Command(f"commit persist {state} ", questions=confirm))
        commit_message = self._commit_label(commit_message)
        if commit_message:
            res.after_cmds.add_cmd(Command(f"commit label {commit_message}"))
        else:
            res.after_cmds.add_cmd(Command("commit"))
        res.after_cmds.add_cmd(self._return())
        res.after_cmds.add_cmd(self._show_checkpoints())
        return res

    def parse_confirm_trial(self, smth: DeviceResult) -> CommitState:
        return self._parse_commits(smth)

    def reset_trial(self, state: TrialState) -> DeviceCommands:
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command("system"))
        rollback = [Question("The trial configuration will be rolled back. Continue?", "Y")]
        res.before_cmds.add_cmd(Command(f"abort trial persist {state}", questions=rollback))
        res.after_cmds.add_cmd(self._return())
        return res

    def rollback(self, state: CommitState) -> DeviceCommands:
        res = DeviceCommands()
        confirm = [Question("This operation will revert configuration changes to the previous status. Continue?", "Y")]
        res.before_cmds.add_cmd(Command(f"rollback configuration to commit-id {state}", questions=confirm))
        return res

    def quit(self) -> DeviceCommands:
        res = DeviceCommands()
        res.after_cmds.add_cmd(Command("quit", suppress_eof=True))
        return res
