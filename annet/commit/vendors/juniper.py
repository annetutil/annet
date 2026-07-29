import json
import logging
import re
from datetime import timedelta

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

logger = logging.getLogger(__name__)

INVALID_COMMIT_COMMENT_SYMBOLS = re.compile(r"[^a-zA-Z0-9.,:;{}()\[\]=+\-<>@ ']+")


def remove_json_tail(data: str) -> str:
    lines = data.splitlines(keepends=False)
    while lines and (not lines[-1] or lines[-1].startswith("#")):
        lines.pop()
    return "\n".join(lines)


class JuniperCommander(VendorCommander):
    def _show_checkpoints(self) -> Command:
        return Command("show system commit revision | display json")

    def _commit_comment(self, msg: str) -> str:
        return INVALID_COMMIT_COMMENT_SYMBOLS.sub(" ", msg).strip()[:256]

    def fetch(
        self,
        device: Device,  # noqa: ARG002
        files: list[str],
    ) -> DeviceCommands:
        ensure_no_files(files)
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command("show configuration"))
        res.before_cmds.add_cmd(self._show_checkpoints())
        return res

    def _parse_commits(self, smth: DeviceResult) -> CommitState:
        """
        find list checkpoints command and parse its output
        """
        cmd_res = find_command_res(smth, self._show_checkpoints().cmd)
        if not cmd_res:
            return ""

        try:
            data = json.loads(remove_json_tail(cmd_res.out))
        except json.decoder.JSONDecodeError:
            logger.warning("Command output is not valid JSON")
            return ""

        try:
            checkpoints = data["commit-revision-information"][0]["revision"]
            if not checkpoints:
                return ""
            return checkpoints[0]["data"]
        except Exception:
            logger.exception("Command output is not valid")
            return ""

    def parse_fetch(self, smth: DeviceResult) -> DeviceConfig:
        return DeviceConfig(
            config=smth.before_cmds[0].out,
            files={},
            commit_state=self._parse_commits(smth),
        )

    def _exit_configure(self) -> Command:
        drop_changes = [Question("Discard uncommitted changes?", "yes")]
        return Command("exit configuration-mode", questions=drop_changes)

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
            res.after_cmds.add_cmd(Command(f'commit comment "{commit_message}"'))
        else:
            res.after_cmds.add_cmd(Command("commit"))
        res.after_cmds.add_cmd(self._exit_configure())
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
        res.before_cmds.add_cmd(self._show_checkpoints())
        res.before_cmds.add_cmd(Command("configure exclusive"))

        minutes = (int(timeout.total_seconds()) // 60) or 1
        commit_message = self._commit_comment(commit_message)
        if commit_message:
            res.after_cmds.add_cmd(Command(f'commit confirmed {minutes} comment "{commit_message}"'))
        else:
            res.after_cmds.add_cmd(Command(f"commit confirmed {minutes}"))
        res.after_cmds.add_cmd(self._exit_configure())
        return res

    def apply_trial_device(
        self,
        device: Device,  # noqa: ARG002
        commit_message: str,  # noqa: ARG002
        timeout: timedelta,  # noqa: ARG002
    ) -> DeviceCommands:
        return DeviceCommands()

    def parse_trial(self, smth: DeviceResult) -> TrialState:
        # trial state contains previous commit id
        return self._parse_commits(smth)

    def confirm_trial(
        self,
        commit_message: str,
        state: TrialState,  # noqa: ARG002
    ) -> DeviceCommands:
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command("configure exclusive"))
        commit_message = self._commit_comment(commit_message)
        if commit_message:
            res.before_cmds.add_cmd(Command(f'commit comment "{commit_message}"'))
        else:
            res.before_cmds.add_cmd(Command("commit"))
        res.after_cmds.add_cmd(self._exit_configure())
        res.after_cmds.add_cmd(self._show_checkpoints())
        return res

    def parse_confirm_trial(self, smth: DeviceResult) -> CommitState:
        return self._parse_commits(smth)

    def reset_trial(self, state: TrialState) -> DeviceCommands:
        return self.rollback(state)

    def rollback(self, state: CommitState) -> DeviceCommands:
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command("configure exclusive"))
        res.before_cmds.add_cmd(Command(f"rollback revision {state}", timeout=20))
        res.before_cmds.add_cmd(Command("commit"))
        res.after_cmds.add_cmd(self._exit_configure())
        return res

    def quit(self) -> DeviceCommands:
        res = DeviceCommands()
        res.after_cmds.add_cmd(Command("quit", suppress_eof=True))
        return res
