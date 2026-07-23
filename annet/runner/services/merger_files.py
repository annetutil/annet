from collections.abc import Sequence
from datetime import timedelta
from typing import cast

from annet.annlib.command import Command
from annet.annlib.command import CommandList
from annet.diff import FileDiffer
from annet.rulebook import RulebookProvider
from annet.storage import Device

from annet.runner.deploy_protocols import DeviceCommands
from annet.runner.deploy_protocols import DeviceConfig
from annet.runner.deploy_protocols import FileCommands
from annet.runner.protocols import Diff
from annet.runner.protocols import FilterAcl
from annet.runner.protocols import GeneratedData
from annet.runner.protocols import GeneratorMerger


def make_pc_cmds(
    device: Device,
    old_text: str,
    new: GeneratedData,
    differ: FileDiffer,
    ignore_cmds: bool,
) -> FileCommands | None:
    if not differ.diff_file(device.hw, new.path, new.output, old_text):
        return None
    if new.output is None:
        msg = f"Cannot process file {new.path} with None output for device {device.fqdn}"
        raise ValueError(msg)
    res = FileCommands(
        before_cmds=CommandList(),
        after_cmds=CommandList(),
        data=new.output.encode("utf-8"),
    )

    if ignore_cmds:
        return res

    if new.before_cmds:
        res.before_cmds.add_cmd(Command(cmd=new.before_cmds))
    if new.after_cmds:
        res.after_cmds.add_cmd(Command(cmd=new.after_cmds))

    return res


def make_pc_diff(
    device: Device,
    old_text: str,
    new: GeneratedData,
    differ: FileDiffer,
) -> str | None:
    diff_lines = differ.diff_file(device.hw, new.path, old_text, new.output)
    if not diff_lines:
        return None
    return "\n".join(diff_lines)


class FilesMerger(GeneratorMerger):
    def __init__(
        self,
        rulebook_provider: RulebookProvider,
        file_differ: FileDiffer,
    ) -> None:
        self._rulebook_provider = rulebook_provider
        self._file_differ = file_differ

    def _get_single_data(self, gen_data: Sequence[GeneratedData]) -> GeneratedData:
        if not gen_data:
            msg = "Cannot calculate patch as no data provided"
            raise ValueError(msg)
        first_data = gen_data[0]
        if len(gen_data) != 1:
            msg = f"Cannot have multiple generators for {first_data.path}"
            raise ValueError(msg)
        if first_data.path is None:
            msg = "Cannot have empty path for file generator"
            raise ValueError(msg)
        return first_data

    def diff(
        self,
        device: Device,
        live_config: DeviceConfig,
        gen_data: Sequence[GeneratedData],
        filter_acl: list[FilterAcl],  # noqa: ARG002
    ) -> dict[str | None, Diff]:
        first_data = self._get_single_data(gen_data)
        path = cast(str, first_data.path)
        diff = make_pc_diff(
            device=device,
            old_text=live_config.files.get(path, ""),
            new=first_data,
            differ=self._file_differ,
        )
        if not diff:
            return {}
        return {
            first_data.path: Diff(path=first_data.path, diff=diff, error=None),
        }

    def patch(
        self,
        device: Device,
        live_config: DeviceConfig,
        gen_data: Sequence[GeneratedData],
        filter_acl: list[FilterAcl],  # noqa: ARG002
        commit_message: str,  # noqa: ARG002
    ) -> DeviceCommands:
        first_data = self._get_single_data(gen_data)
        path = cast(str, first_data.path)
        pc_cmds = make_pc_cmds(
            device=device,
            old_text=live_config.files.get(path, ""),
            new=first_data,
            differ=self._file_differ,
            ignore_cmds=True,  # TODO: remove when switch to new etcrepo logic
        )
        return DeviceCommands(
            before_cmds=CommandList(),
            upload_files={path: pc_cmds} if pc_cmds else {},
            after_cmds=CommandList(),
            download_files=[],
        )

    def patch_trial(
        self,
        device: Device,
        live_config: DeviceConfig,
        gen_data: Sequence[GeneratedData],
        filter_acl: list[FilterAcl],  # noqa: ARG002
        commit_message: str,  # noqa: ARG002
        timeout: timedelta,  # noqa: ARG002
    ) -> DeviceCommands:
        first_data = self._get_single_data(gen_data)
        path = cast(str, first_data.path)
        pc_cmds = make_pc_cmds(
            device=device,
            old_text=live_config.files.get(path, ""),
            new=first_data,
            differ=self._file_differ,
            ignore_cmds=True,  # TODO: remove when switch to new etcrepo logic
        )
        if not pc_cmds:
            return DeviceCommands()

        return DeviceCommands(
            before_cmds=CommandList(),
            upload_files={path: pc_cmds},
            after_cmds=CommandList(),
            download_files=[],
        )

    def make_device_config(
        self,
        device: Device,  # noqa: ARG002
        gen_data: Sequence[GeneratedData],
    ) -> DeviceConfig:
        first_data = self._get_single_data(gen_data)
        path = cast(str, first_data.path)
        if first_data.output is None:
            msg = f"Cannot process file {first_data.path} with None output"
            raise ValueError(msg)
        return DeviceConfig(
            config=None,
            files={path: first_data.output},
        )
