import logging
import textwrap
from collections import OrderedDict
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from annet import generators
from annet import implicit
from annet import patching
from annet.annlib.command import Command
from annet.annlib.command import CommandList
from annet.annlib.diff import gen_pre_as_diff
from annet.annlib.diff import resort_diff
from annet.annlib.lib import merge_dicts
from annet.api import patch_from_pre
from annet.deploy import fill_cmd_params
from annet.deploy import make_cmd_params
from annet.patching import Orderer
from annet.rulebook import RulebookProvider
from annet.rulebook import deploying
from annet.storage import Device
from annet.vendors import Registry
from annet.vendors import tabparser
from annet.vendors.tabparser import CommonFormatter

from annet.runner.deploy_protocols import DeviceCommands
from annet.runner.deploy_protocols import DeviceConfig
from annet.runner.deploy_protocols import VendorCommander
from annet.runner.deploy_protocols import VendorCommanderRegistry
from annet.runner.protocols import Diff
from annet.runner.protocols import FilterAcl
from annet.runner.protocols import GeneratedData
from annet.runner.protocols import GeneratorMerger

logger = logging.getLogger(__name__)


@dataclass
class TargetDeviceConfig:
    acl: dict | None
    config: dict | None


def _combine_acl_text(partial_results: Sequence[GeneratedData | FilterAcl]) -> str:
    acl_text = ""
    for res in partial_results:
        for line in textwrap.dedent(res.acl or "").split("\n"):
            if line and not line.isspace():
                acl_text += line.rstrip()
                acl_text += f"  %generator_names={res.name}"
                acl_text += "\n"
    return acl_text


def make_diff_pre(
    old: dict,
    new: TargetDeviceConfig,
    filter_acl: dict | None,
    orderer: Orderer,
    rb: dict,
) -> dict[str, Any] | None:
    old_filtered = patching.apply_acl(old, new.acl)
    new_filtered = patching.apply_acl(new.config, new.acl)
    if filter_acl:
        old_filtered = patching.apply_acl(old_filtered, filter_acl)
        new_filtered = patching.apply_acl(new_filtered, filter_acl)

    diff_tree = patching.make_diff(
        orderer.order_config(old_filtered),
        orderer.order_config(new_filtered),
        rb,
        [new.acl],
    )
    diff_tree = patching.strip_unchanged(diff_tree)
    if not diff_tree:
        return None
    diff_tree = resort_diff(diff_tree)
    return patching.make_pre(diff_tree)


def _get_cmd_paths(
    device: Device,
    old: dict,
    new: TargetDeviceConfig,
    filter_acl: dict | None,
    formatter: CommonFormatter,
    rulebook_provider: RulebookProvider,
) -> OrderedDict:
    rb = rulebook_provider.get_rulebook(device.hw)
    orderer = Orderer(rb["ordering"], device.hw.vendor)
    pre = make_diff_pre(old=old, new=new, rb=rb, orderer=orderer, filter_acl=filter_acl)

    logger.info("patch_from_pre")
    if not pre:
        return OrderedDict()
    patch_tree = patch_from_pre(pre, device.hw, rb, add_comments=True, do_commit=True)
    return formatter.cmd_paths(patch_tree)


def _apply_deploy_rulebook(
    rulebook: RulebookProvider,
    vendor: VendorCommander,
    device: Device,
    timeout: timedelta | None,
    commit_message: str,
    cmd_paths: OrderedDict,
) -> CommandList:
    rules = rulebook.get_rulebook(device.hw)["deploying"]
    apply_paths: dict[object, CommandList] = defaultdict(CommandList)
    for cmd_path, context in cmd_paths.items():
        rule = deploying.match_deploy_rule(rules, cmd_path, context)
        apply_logic = rule["attrs"]["apply_logic"]
        cmd_params = make_cmd_params(rule)
        cmd = Command(cmd_path[-1], **cmd_params)
        apply_paths[apply_logic].add_cmd(cmd)

    res = CommandList()
    for apply_logic, cmds in apply_paths.items():
        if timeout is not None:
            wrap_cmds = vendor.apply_trial_part(device, apply_logic, commit_message, timeout=timeout)
        else:
            wrap_cmds = vendor.apply_commit_part(device, apply_logic, commit_message)

        for cmd in wrap_cmds.before_cmds.cmss:
            fill_cmd_params(rules, cmd)
            res.add_cmd(cmd)
        for cmd in cmds.cmss:
            res.add_cmd(cmd)
        for cmd in wrap_cmds.after_cmds.cmss:
            fill_cmd_params(rules, cmd)
            res.add_cmd(cmd)
    return res


def make_commit_cmds(
    device: Device,
    old: dict,
    new: TargetDeviceConfig,
    filter_acl: dict | None,
    rulebook: RulebookProvider,
    formatter: CommonFormatter,
    vendor_commander: VendorCommander,
    commit_message: str,
    timeout: timedelta | None,
) -> DeviceCommands:
    cmd_paths = _get_cmd_paths(device, old, new, filter_acl, formatter, rulebook)
    if not cmd_paths:
        return DeviceCommands()

    logger.info("apply_deploy_rulebook for trial")
    cmds = _apply_deploy_rulebook(
        device=device,
        cmd_paths=cmd_paths,
        timeout=timeout,
        rulebook=rulebook,
        vendor=vendor_commander,
        commit_message=commit_message,
    )
    return DeviceCommands(
        before_cmds=cmds,
        upload_files={},
        download_files=[],
        after_cmds=CommandList(),
    )


def make_cli_diff(
    device: Device,
    old: dict,
    new: TargetDeviceConfig,
    filter_acl: dict | None,
    rulebook_provider: RulebookProvider,
) -> str | None:
    rb = rulebook_provider.get_rulebook(device.hw)
    orderer = Orderer(rb["ordering"], device.hw.vendor)
    pre = make_diff_pre(old=old, new=new, filter_acl=filter_acl, rb=rb, orderer=orderer)
    if not pre:
        return None
    diff = gen_pre_as_diff(pre, False, "   ", True)
    return "".join(diff)


class CliConfigMerger(GeneratorMerger):
    def __init__(
        self,
        vendor_registry: Registry,
        rulebook_provider: RulebookProvider,
        vendor_commander_registry: VendorCommanderRegistry,
    ) -> None:
        self._vendor_registry = vendor_registry
        self._rulebook_provider = rulebook_provider
        self._commander_registry = vendor_commander_registry

    def diff(
        self,
        device: Device,
        live_config: DeviceConfig,
        gen_data: Sequence[GeneratedData],
        filter_acl: list[FilterAcl],
    ) -> dict[str | None, Diff]:
        old_res = self._live_to_config(device, live_config)
        new_res = self._generators_to_config(device, gen_data)
        diff = make_cli_diff(
            rulebook_provider=self._rulebook_provider,
            device=device,
            old=old_res,
            new=new_res,
            filter_acl=self._prepare_filter_acl(device, filter_acl),
        )
        if not diff:
            return {}
        return {
            None: Diff(error=None, path=None, diff=diff),
        }

    def patch(
        self,
        device: Device,
        live_config: DeviceConfig,
        gen_data: Sequence[GeneratedData],
        filter_acl: list[FilterAcl],
        commit_message: str,
    ) -> DeviceCommands:
        old_res = self._live_to_config(device, live_config)
        new_res = self._generators_to_config(device, gen_data)
        vendor = self._vendor_registry.match(device.hw)
        formatter = vendor.make_formatter()
        vendor_commander = self._commander_registry.match(device.hw)
        return make_commit_cmds(
            device=device,
            old=old_res,
            new=new_res,
            formatter=formatter,
            vendor_commander=vendor_commander,
            timeout=None,
            rulebook=self._rulebook_provider,
            filter_acl=self._prepare_filter_acl(device, filter_acl),
            commit_message=commit_message,
        )

    def patch_trial(
        self,
        device: Device,
        live_config: DeviceConfig,
        gen_data: Sequence[GeneratedData],
        filter_acl: list[FilterAcl],
        commit_message: str,
        timeout: timedelta,
    ) -> DeviceCommands:
        old_res = self._live_to_config(device, live_config)
        new_res = self._generators_to_config(device, gen_data)
        vendor = self._vendor_registry.match(device.hw)
        formatter = vendor.make_formatter()
        vendor_commander = self._commander_registry.match(device.hw)
        return make_commit_cmds(
            device=device,
            old=old_res,
            new=new_res,
            formatter=formatter,
            vendor_commander=vendor_commander,
            timeout=timeout,
            rulebook=self._rulebook_provider,
            filter_acl=self._prepare_filter_acl(device, filter_acl),
            commit_message=commit_message,
        )

    def make_device_config(
        self,
        device: Device,
        gen_data: Sequence[GeneratedData],
    ) -> DeviceConfig:
        formatter = self._vendor_registry.match(device.hw).make_formatter()
        cfg = self._generators_to_config(device, gen_data)
        if not cfg.config:
            return DeviceConfig(config=None, files={})
        return DeviceConfig(
            config=formatter.join(cfg.config),
            files={},
        )

    def _generators_to_config(
        self,
        device: Device,
        generated_data: Sequence[GeneratedData],
    ) -> TargetDeviceConfig:
        formatter = self._vendor_registry.match(device.hw).make_formatter()
        tree: dict[str, Any] = OrderedDict()
        for result in generated_data:
            if not result.output:
                continue
            config = tabparser.parse_to_tree(
                text=result.output,
                splitter=formatter.split,
            )
            tree = merge_dicts(tree, config)
        tree = self._add_implicit(device, tree)

        acl = generators.compile_acl_text(
            _combine_acl_text(generated_data),
            device.hw.vendor,
        )
        return TargetDeviceConfig(
            config=tree,
            acl=acl,
        )

    def _prepare_filter_acl(self, device: Device, filter_acl: list[FilterAcl]) -> dict | None:
        if not filter_acl:
            return None
        return generators.compile_acl_text(
            _combine_acl_text(filter_acl),
            device.hw.vendor,
        )

    def _live_to_config(
        self,
        device: Device,
        live_data: DeviceConfig,
    ) -> dict:
        if not live_data.config:
            return {}
        formatter = self._vendor_registry.match(device.hw).make_formatter()
        parsed_config = tabparser.parse_to_tree(
            text=live_data.config,
            splitter=formatter.split,
        )
        return self._add_implicit(device, parsed_config)

    def _add_implicit(self, device: Device, config: dict) -> dict:
        implicit_rules = implicit.compile_rules(device)
        return merge_dicts(config, implicit.config(config, implicit_rules))
