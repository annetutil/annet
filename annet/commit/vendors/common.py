from annet.runner.deploy_protocols import CommandResult
from annet.runner.deploy_protocols import DeviceResult


class BlackboxFilesError(ValueError):
    def __init__(self) -> None:
        super().__init__("Blackbox device cannot have files")


def ensure_no_files(files: list[str]) -> None:
    if files:
        raise BlackboxFilesError


class TrialUnsupportedError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Trial is unsupported")


class RollbackUnsupportedError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Rollback is unsupported")


def find_command_res(
    result: DeviceResult,
    expected_cmd: str,
    *,
    exact: bool = True,
) -> CommandResult | None:
    for cmd_res in result.before_cmds:
        if (cmd_res.cmd == expected_cmd and exact) or (cmd_res.cmd.startswith(expected_cmd)):
            if cmd_res.error:
                return None
            return cmd_res
    for cmd_res in result.after_cmds:
        if (cmd_res.cmd == expected_cmd and exact) or (cmd_res.cmd.startswith(expected_cmd)):
            if cmd_res.error:
                return None
            return cmd_res
    return None
