# ruff: noqa: T201
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from logging import getLogger
from time import sleep

import colorama
from annet.annlib.command import CommandList
from annet.deploy import ProgressBar
from annet.deploy_ui import ProgressBars
from annet.storage import Device

from annet.runner.deploy_protocols import DeployResult
from annet.runner.deploy_protocols import DeviceCommands
from annet.runner.deploy_protocols import DeviceConfig
from annet.runner.protocols import DeployUI
from annet.runner.protocols import DeviceID
from annet.runner.protocols import Diff
from annet.runner.protocols import DiffUI
from annet.runner.protocols import GenerationResult
from annet.runner.protocols import RollbackShowUI
from annet.runner.protocols import ShowGenDiff
from annet.runner.protocols import TrialConfirmationAction
from annet.runner.ui.common import format_header
from annet.runner.ui.common import show_header
from annet.runner.ui.common import show_result

logger = getLogger(__name__)


def _format_text_diff(diff: str) -> str:
    diff_lines = diff.splitlines(keepends=False)
    colors = (
        ("+++", colorama.Fore.CYAN),
        ("---", colorama.Fore.CYAN),
        ("@@", colorama.Fore.CYAN),
        ("+", colorama.Fore.GREEN),
        ("-", colorama.Fore.RED),
        (">", colorama.Fore.YELLOW),
    )
    colored_lines = []
    for line in diff_lines:
        for check, color in colors:
            if line.startswith(check):
                colored_lines.append(color + line + colorama.Fore.RESET)
                break
        else:
            colored_lines.append(line)
    return "\n".join(colored_lines)


def _format_command_list(cmds: CommandList) -> str:
    return "\n".join(cmd.cmd for cmd in cmds)


def _format_commands(
    devices: list[Device],
    commands: dict[DeviceID, DeviceCommands],
) -> dict[str, list[tuple[str, str]]]:
    res = {}
    for device in devices:
        dev_cmds = commands.get(device.id)
        if not dev_cmds:
            continue
        dev_res: list[tuple[str, str]] = []
        if dev_cmds.before_cmds:
            dev_res.append(("before all", _format_command_list(dev_cmds.before_cmds)))
        if dev_cmds.upload_files:
            for file, file_cmds in dev_cmds.upload_files.items():
                file_header = f"{colorama.Style.BRIGHT}{file}{colorama.Style.NORMAL}"
                if file_cmds.before_cmds:
                    dev_res.append((f"before {file_header}", _format_command_list(file_cmds.before_cmds)))
                dev_res.append((file_header, file_cmds.data.decode("utf-8")))
                if file_cmds.after_cmds:
                    dev_res.append((f"after {file_header}", _format_command_list(file_cmds.after_cmds)))
            if dev_cmds.after_cmds:
                dev_res.append(("after all", _format_command_list(dev_cmds.after_cmds)))
        if dev_res:
            res[device.fqdn] = dev_res
    return res


def show_commands(devices: list[Device], commands: dict[DeviceID, DeviceCommands]) -> None:
    result = _format_commands(devices, commands)
    for fqdn, command_groups in result.items():
        show_header(format_header(fqdn, "", ""), colorama.Back.GREEN)
        prev_header = ""
        for group_header, group_cmds in command_groups:
            if prev_header != group_header and len(command_groups) > 1:
                show_header(group_header, colorama.Back.LIGHTBLACK_EX)
                prev_header = group_header
            print(group_cmds)
        print()


def _unite_output(data: dict[str, str], *additional: dict[str, str]) -> dict[str, str]:
    data = data.copy()
    for more_data in additional:
        for key, value in more_data.items():
            if key in data:
                data[key] += "\n" + value
            else:
                data[key] = value
    return data


def _format_diff(devices: list[Device], diff: dict[DeviceID, dict[str | None, Diff]]) -> dict[str, str]:
    res: dict[str, str] = {}
    for device in devices:
        dev_diff = diff.get(device.id)
        if not dev_diff:
            continue
        for file, file_diff in dev_diff.items():
            if not file_diff.diff:
                continue
            colored_diff = _format_text_diff(file_diff.diff)
            res[format_header(device.fqdn, "", file)] = colored_diff
    return res


def show_diff(devices: list[Device], diff: dict[DeviceID, dict[str | None, Diff]]) -> None:
    formatted_diffs = _format_diff(devices, diff)
    show_result(formatted_diffs, colorama.Back.GREEN)


def _format_per_gen_diff(devices: list[Device], diff: dict[DeviceID, list[ShowGenDiff]]) -> dict[str, str]:
    res: dict[str, str] = {}
    for device in devices:
        dev_diff = diff.get(device.id)
        if not dev_diff:
            continue
        for gen_diff in dev_diff:
            if not gen_diff.diff:
                continue
            colored_diff = _format_text_diff(gen_diff.diff)
            res[format_header(device.fqdn, gen_diff.name, gen_diff.path)] = colored_diff
    return res


def show_per_gen_diff(devices: list[Device], diff: dict[DeviceID, list[ShowGenDiff]]) -> None:
    formatted_diffs = _format_per_gen_diff(devices, diff)
    show_result(formatted_diffs, colorama.Back.GREEN)


def _format_live_errors(
    devices: list[Device],
    live_configs: dict[DeviceID, DeviceConfig],
) -> dict[str, str]:
    res: dict[str, str] = {}
    for device in devices:
        header = format_header(device.fqdn, "", "")
        if device.id not in live_configs:
            res[header] = "No live config found"
        else:
            live = live_configs[device.id]
            if live.error:
                res[header] = "Live config error: " + live.error
    return res


def _format_gen_errors(
    devices: list[Device],
    gen_res: dict[DeviceID, GenerationResult],
) -> dict[str, str]:
    res: dict[str, str] = {}
    for device in devices:
        errors = []
        if device.id not in gen_res:
            errors.append("No generation result found")
        else:
            gen = gen_res[device.id]
            if gen.error:
                errors.append("Generation error: " + gen.error)
            for single_res in gen.data:
                if single_res.error is not None:
                    res[format_header(device.fqdn, single_res.name, single_res.path)] = single_res.error
        if errors:
            res[format_header(device.fqdn, "", "")] = "\n".join(errors)
    return res


def _format_per_gen_diff_error(devices: list[Device], diff: dict[DeviceID, list[ShowGenDiff]]) -> dict[str, str]:
    res: dict[str, str] = {}
    for device in devices:
        dev_diff = diff.get(device.id)
        if not dev_diff:
            continue
        for gen_diff in dev_diff:
            if not gen_diff.error:
                continue
            res[format_header(device.fqdn, f"diff {gen_diff.name}", gen_diff.path)] = gen_diff.error
    return res


def _format_diff_errors(
    devices: list[Device],
    diff: dict[DeviceID, dict[str | None, Diff]],
) -> dict[str, str]:
    res: dict[str, str] = {}
    for device in devices:
        dev_diff = diff.get(device.id)
        if not dev_diff:
            continue
        for file, file_diff in dev_diff.items():
            if not file_diff.error:
                continue
            res[format_header(device.fqdn, "diff", file)] = file_diff.error
    return res


def show_errors(
    devices: list[Device],
    live_configs: dict[DeviceID, DeviceConfig],
    gen_res: dict[DeviceID, GenerationResult],
    diff: dict[DeviceID, dict[str | None, Diff]],
    cmds: dict[DeviceID, DeviceCommands],  # noqa: ARG001
    gen_diff: dict[DeviceID, list[ShowGenDiff]],
) -> None:
    errors = _unite_output(
        _format_live_errors(devices, live_configs),
        _format_gen_errors(devices, gen_res),
        _format_diff_errors(devices, diff),
        _format_per_gen_diff_error(devices, gen_diff),
    )
    show_result(errors, colorama.Back.RED)


def show_deploy_result(devices: list[Device], results: dict[DeviceID, DeployResult]) -> None:
    for device in devices:
        header = format_header(device.fqdn, "", "")
        if device.id not in results:
            show_header(header, colorama.Back.RED)
            print("NOT DEPLOYED")
            continue

        res = results[device.id]
        if res.errors:
            show_header(header, colorama.Back.RED)
            for error in res.errors:
                print("*", error)
        else:
            show_header(header, colorama.Back.GREEN)

        if res.trial_state:
            print(f"TRIAL: {res.trial_state}")
        if res.commit_state:
            print(f"COMMIT: {res.commit_state}")


class ConsoleDeployUI(DeployUI):
    def __init__(
        self,
        no_progress: bool,
        deploy_auto_confirmation: bool | None,
        auto_confirm_trial: timedelta | None = None,
    ) -> None:
        """
        :param no_progress: True to hide progress bars
        :param deploy_auto_confirmation: True auto confifirm deploy, False to auto decline, None to ask user
        :param auto_confirm_trial: delay duration to auto confirm deploy, None to ask user
        """
        self._deploy_auto_confirmation = deploy_auto_confirmation
        self._auto_confirm_trial = auto_confirm_trial
        self._no_progress = no_progress

    @asynccontextmanager
    async def progress_bar(self, devices: list[Device]) -> AsyncIterator[ProgressBar | None]:
        if self._no_progress:
            yield None
            return

        progress_bar = ProgressBars({device.fqdn: {} for device in devices})
        progress_bar.init()
        with progress_bar:
            progress_bar.start_terminal_refresher()
            yield progress_bar
            await progress_bar.wait_for_exit()
        progress_bar.screen.clear()
        progress_bar.stop_terminal_refresher()

    def show(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        diff: dict[DeviceID, dict[str | None, Diff]],
        cmds: dict[DeviceID, DeviceCommands],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
    ) -> None:
        show_errors(devices, live_configs, gen_data, diff, cmds, gen_diff)
        show_diff(devices, diff)

    def show_errors(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        diff: dict[DeviceID, dict[str | None, Diff]],
        cmds: dict[DeviceID, DeviceCommands],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
    ) -> None:
        show_errors(devices, live_configs, gen_data, diff, cmds, gen_diff)

    def confirm_deployment(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        diff: dict[DeviceID, dict[str | None, Diff]],
        cmds: dict[DeviceID, DeviceCommands],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
    ) -> bool:
        if self._deploy_auto_confirmation is not None:
            return self._deploy_auto_confirmation
        show_errors(devices, live_configs, gen_data, diff, cmds, gen_diff)
        answer = "d"
        while True:
            if answer == "y":
                return True
            if answer == "d":
                show_diff(devices, diff)
            elif answer == "g":
                show_per_gen_diff(devices, gen_diff)
            elif answer == "c":
                show_commands(devices, cmds)
            elif answer == "n":
                return False
            answer = input("Continue? y(yes)/n(no)/g(generators)/c(commands)/d(diff)")

    def confirm_trial_confirmation(
        self,
        devices: list[Device],
        confirm_cmds: dict[DeviceID, DeviceCommands],
        reset_cmds: dict[DeviceID, DeviceCommands],
    ) -> TrialConfirmationAction:
        show_commands(devices, confirm_cmds)
        if self._auto_confirm_trial is not None:
            logger.info("Automatic confirmation, wait %s seconds", self._auto_confirm_trial.total_seconds())
            sleep(self._auto_confirm_trial.total_seconds())
            return TrialConfirmationAction.CONFIRM
        while True:
            answer = input("Confirm the deployment? c(confirm)/r(rollback)/q(quit)")
            if answer.lower() == "c":
                return TrialConfirmationAction.CONFIRM
            if answer.lower() == "r":
                show_commands(devices, reset_cmds)
                return TrialConfirmationAction.ROLLBACK
            if answer.lower() == "q":
                return TrialConfirmationAction.QUIT

    def show_deploy_result(
        self,
        devices: list[Device],
        results: dict[DeviceID, DeployResult],
    ) -> None:
        show_deploy_result(devices, results)


class ConsoleDiffUI(DiffUI):
    def __init__(self, *, per_gen: bool) -> None:
        self._per_gen: bool = per_gen

    async def show_diff(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        diff: dict[DeviceID, dict[str | None, Diff]],
        cmds: dict[DeviceID, DeviceCommands],  # noqa: ARG002
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
        has_errors: bool,  # noqa: ARG002,
    ) -> None:
        if self._per_gen:
            show_errors(devices, live_configs, gen_data, {}, {}, gen_diff)
            show_per_gen_diff(devices, gen_diff)
        else:
            show_errors(devices, live_configs, gen_data, diff, {}, {})
            show_diff(devices, diff)
        print()


class ConsolePatchUI(DiffUI):
    async def show_diff(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        diff: dict[DeviceID, dict[str | None, Diff]],  # noqa: ARG002
        cmds: dict[DeviceID, DeviceCommands],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],  # noqa: ARG002,
        has_errors: bool,  # noqa: ARG002,
    ) -> None:
        show_errors(devices, live_configs, gen_data, {}, cmds, {})
        show_commands(devices, cmds)


class ConsoleRollbackShowUI(RollbackShowUI):
    def show_rollback_commands(
        self,
        devices: list[Device],
        rollback_cmds: dict[DeviceID, DeviceCommands],
    ) -> None:
        show_commands(devices, rollback_cmds)
