import json
from collections.abc import Sequence
from datetime import timedelta

from annet.annlib import jsontools
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


def unite_json_fragments(
    old: dict,
    gen_data: Sequence[GeneratedData],
    filter_acl: list[str] | None,
) -> dict:
    for new in gen_data:
        if not new.output:
            continue
        acl = json.loads(new.acl) if new.acl else None
        new_part = json.loads(new.output)
        old = jsontools.apply_json_fragment(old, new_part, acl=acl, filters=filter_acl)
    return old


def make_json_commands(
    old: dict,
    gen_data: Sequence[GeneratedData],
    filter_acl: list[str] | None,
) -> FileCommands | None:
    json_res = unite_json_fragments(old, gen_data, filter_acl)
    old_text = jsontools.format_json(old)
    new_text = jsontools.format_json(json_res)
    if old_text == new_text:
        return None
    res = FileCommands(data=new_text.encode("utf-8"))
    seen_before_cmd = set()
    seen_after_cmd = set()
    for new in gen_data:
        # do not add same command multiple times in a row
        if new.before_cmds and new.before_cmds not in seen_before_cmd:
            res.before_cmds.add_cmd(Command(cmd=new.before_cmds))
            seen_before_cmd.add(new.before_cmds)
        if new.after_cmds and new.after_cmds not in seen_after_cmd:
            res.after_cmds.add_cmd(Command(cmd=new.after_cmds))
            seen_after_cmd.add(new.after_cmds)
    return res


def make_diff(differ: FileDiffer, device: Device, path: str, old: dict, new: dict) -> str | None:
    old_text = jsontools.format_json(old)
    new_text = jsontools.format_json(new)
    diff_lines = differ.diff_file(device.hw, path, old_text, new_text)
    if not diff_lines:
        return None
    return "\n".join(diff_lines)


class JsonFilesMerger(GeneratorMerger):
    def __init__(
        self,
        rulebook_provider: RulebookProvider,
        file_differ: FileDiffer,
    ) -> None:
        self._rulebook_provider = rulebook_provider
        self._file_differ = file_differ

    def _get_path(self, gen_data: Sequence[GeneratedData]) -> str:
        if not gen_data:
            msg = "No generated data found, cannot merge"
            raise ValueError(msg)
        path = gen_data[0].path
        if path is None:
            msg = "Cannot have empty path for file generator"
            raise ValueError(msg)
        return path

    def diff(
        self,
        device: Device,
        live_config: DeviceConfig,
        gen_data: Sequence[GeneratedData],
        filter_acl: list[FilterAcl],
    ) -> dict[str | None, Diff]:
        path = self._get_path(gen_data)
        old = self._live_to_config(device, live_config, path)
        new = unite_json_fragments(old, gen_data, self._prepare_filter_acl(device, filter_acl))
        diff = make_diff(
            device=device,
            old=old,
            new=new,
            path=path,
            differ=self._file_differ,
        )
        if not diff:
            return {}
        return {
            path: Diff(error=None, path=path, diff=diff),
        }

    def patch(
        self,
        device: Device,
        live_config: DeviceConfig,
        gen_data: Sequence[GeneratedData],
        filter_acl: list[FilterAcl],
        commit_message: str,  # noqa: ARG002
    ) -> DeviceCommands:
        path = self._get_path(gen_data)
        old = self._live_to_config(device, live_config, path)
        pc_cmds = make_json_commands(old, gen_data, self._prepare_filter_acl(device, filter_acl))
        if not pc_cmds:
            return DeviceCommands()
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
        filter_acl: list[FilterAcl],
        commit_message: str,  # noqa: ARG002
        timeout: timedelta,  # noqa: ARG002
    ) -> DeviceCommands:
        path = self._get_path(gen_data)
        old = self._live_to_config(device, live_config, path)
        pc_cmds = make_json_commands(old, gen_data, self._prepare_filter_acl(device, filter_acl))
        if not pc_cmds:
            return DeviceCommands()
        return DeviceCommands(
            before_cmds=CommandList(),
            upload_files={path: pc_cmds} if pc_cmds else {},
            after_cmds=CommandList(),
            download_files=[],
        )

    def make_device_config(
        self,
        device: Device,  # noqa: ARG002
        gen_data: Sequence[GeneratedData],
    ) -> DeviceConfig:
        path = self._get_path(gen_data)
        new = unite_json_fragments({}, gen_data, [])
        return DeviceConfig(
            files={path: jsontools.format_json(new)},
        )

    def _live_to_config(
        self,
        device: Device,  # noqa: ARG002
        live_data: DeviceConfig,
        path: str,
    ) -> dict:
        if path not in live_data.files:
            return {}
        return json.loads(live_data.files[path])

    def _prepare_filter_acl(
        self,
        device: Device,  # noqa: ARG002
        filter_acl: list[FilterAcl],
    ) -> list[str] | None:
        if not filter_acl:
            return None
        res = []
        for acl in filter_acl:
            res.extend(acl.acl.splitlines())
        return res
