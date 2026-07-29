import json
import logging
import re
from datetime import timedelta
from uuid import uuid4

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

logger = logging.getLogger(__name__)

INVALID_CHECKPOINT_SYMBOLS = re.compile(r"[^a-zA-Z0-9.\-]+")


class AristaCommander(VendorCommander):
    def _show_checkpoints(self) -> Command:
        return Command("show configuration checkpoints | json | no-more")

    def _new_trial_state(self) -> TrialState:
        return f"ann-{uuid4()}"

    def _save_checkpoint(self, msg: str, state: TrialState) -> Command | None:
        name = INVALID_CHECKPOINT_SYMBOLS.sub("_", msg).strip("_")[:100]
        if not name:
            return None
        # save with uniq prefix
        return Command(f"configure checkpoint save {name}-{state}")

    def fetch(
        self,
        device: Device,  # noqa: ARG002
        files: list[str],
    ) -> DeviceCommands:
        ensure_no_files(files)
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command("show running-config | no-more"))
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

        try:
            data = json.loads(cmd_res.out)
        except json.decoder.JSONDecodeError:
            logger.warning("Command output is not valid JSON")
            return ""

        try:
            checkpoint = data["checkpoints"]
            return max(checkpoint.keys(), key=lambda x: checkpoint[x]["fileDate"])
        except Exception:
            logger.exception("Command output is not valid")
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
        session_id = self._new_trial_state()
        configure_cmd = f"configure session {session_id}"
        if commit_message:
            configure_cmd = f"{configure_cmd} description {commit_message}"
        res.before_cmds.add_cmd(Command(configure_cmd))

        res.after_cmds.add_cmd(Command("commit"))
        if save_ckp := self._save_checkpoint(commit_message, session_id):
            res.after_cmds.add_cmd(save_ckp)
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
        session_id = self._new_trial_state()
        configure_cmd = f"configure session {session_id}"
        if commit_message:
            configure_cmd = f"{configure_cmd} description {commit_message}"
        res.before_cmds.add_cmd(Command(configure_cmd))

        hours = timeout.seconds // 60 // 60
        mins = timeout.seconds // 60 % 60
        secs = timeout.seconds % 60 % 60
        res.after_cmds.add_cmd(Command(f"commit timer {hours}:{mins}:{secs}"))
        return res

    def apply_trial_device(
        self,
        device: Device,  # noqa: ARG002
        commit_message: str,  # noqa: ARG002
        timeout: timedelta,  # noqa: ARG002
    ) -> DeviceCommands:
        return DeviceCommands()

    def parse_trial(self, smth: DeviceResult) -> TrialState:
        prefix = "configure session "
        cmd_res = find_command_res(smth, prefix, exact=False)
        if not cmd_res:
            return ""
        return cmd_res.cmd.removeprefix(prefix).strip().split()[0]

    def confirm_trial(self, commit_message: str, state: TrialState) -> DeviceCommands:
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command(f"configure session {state} commit"))
        if save_ckp := self._save_checkpoint(commit_message, state):
            res.after_cmds.add_cmd(save_ckp)
        res.after_cmds.add_cmd(self._show_checkpoints())
        return res

    def parse_confirm_trial(self, smth: DeviceResult) -> CommitState:
        return self._parse_commits(smth)

    def reset_trial(self, state: TrialState) -> DeviceCommands:
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command(f"no configure session {state}"))
        return res

    def rollback(self, state: CommitState) -> DeviceCommands:
        res = DeviceCommands()
        res.before_cmds.add_cmd(Command(f"configure checkpoint restore {state}", timeout=20))
        return res

    def quit(self) -> DeviceCommands:
        res = DeviceCommands()
        res.after_cmds.add_cmd(Command("quit", suppress_eof=True))
        return res
