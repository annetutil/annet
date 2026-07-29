from abc import ABC
from abc import abstractmethod
from collections.abc import Sequence
from datetime import timedelta
from logging import getLogger
from typing import Any

from annet.storage import Device
from annet.storage import Storage

from annet.runner.deploy_protocols import DeployResult
from annet.runner.deploy_protocols import DeviceCommands
from annet.runner.deploy_protocols import DeviceConfig
from annet.runner.deploy_protocols import DeviceDriver
from annet.runner.deploy_protocols import DeviceDriverFactory
from annet.runner.deploy_protocols import DeviceResult
from annet.runner.deploy_protocols import VendorCommanderRegistry
from annet.runner.protocols import CommitMessageSource
from annet.runner.protocols import DeployUI
from annet.runner.protocols import DeviceID
from annet.runner.protocols import DeviceStateLoader
from annet.runner.protocols import Diff
from annet.runner.protocols import DiffUI
from annet.runner.protocols import FilterAcl
from annet.runner.protocols import FilterAclSource
from annet.runner.protocols import GeneratedData
from annet.runner.protocols import GeneratedDataSource
from annet.runner.protocols import GenerationResult
from annet.runner.protocols import GeneratorMerger
from annet.runner.protocols import HandlerError
from annet.runner.protocols import ShowGenDiff
from annet.runner.protocols import TrialConfirmationAction

logger = getLogger(__name__)


def make_gen_diff(
    merger: GeneratorMerger,
    device: Device,
    live: DeviceConfig,
    gen_data: Sequence[GeneratedData],
    filter_acl: list[FilterAcl],
) -> list[ShowGenDiff]:
    if live.error:
        return []
    res = []
    for data in gen_data:
        if data.error:
            continue
        diff = merger.diff(device, live, [data], filter_acl)
        if not diff:
            continue
        res.append(
            ShowGenDiff(
                path=data.path,
                name=data.name,
                tags=data.tags,
                diff=diff[data.path].diff,
                error=diff[data.path].error,
            ),
        )
    return res


def apply_initial(
    devices: list[Device],
    old: dict[DeviceID, DeviceConfig],
    initial: dict[DeviceID, GenerationResult],
    merger: GeneratorMerger,
) -> dict[DeviceID, DeviceConfig]:
    res = old.copy()
    for device in devices:
        device_res = res.get(device.id)
        if not device_res or (not device_res.config and not device_res.files and not device_res.error):
            dev_initial = initial[device.id]
            if dev_initial.error:
                res[device.id].error = dev_initial.error
                continue
            res[device.id] = merger.make_device_config(
                device,
                initial[device.id].data,
            )
    return res


class _CliDiffDeploy(ABC):
    def __init__(
        self,
        storage: Storage,
        fetcher: DeviceStateLoader,
        data_src: GeneratedDataSource,
        filter_acl_src: FilterAclSource,
        initial_data_src: GeneratedDataSource,
        merger: GeneratorMerger,
        commit_message_source: CommitMessageSource,
    ) -> None:
        self._storage = storage
        self._fetcher = fetcher
        self._data_src = data_src
        self._filter_acl_src = filter_acl_src
        self._initial_data_src = initial_data_src
        self._merger = merger
        self._commit_message_source = commit_message_source

    def _apply_initial(
        self,
        devices: list[Device],
        old: dict[DeviceID, DeviceConfig],
    ) -> dict[DeviceID, DeviceConfig]:
        return apply_initial(
            devices,
            old,
            self._initial_data_src.generate(devices),
            self._merger,
        )

    def _has_gen_errors(
        self,
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        device_diff: dict[DeviceID, dict[str | None, Diff]],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
        cmds: dict[DeviceID, DeviceCommands],
    ) -> bool:
        return (
            any(c.error for c in live_configs.values())
            or any(c.error for c in gen_data.values())
            or any(c.error for single in gen_data.values() for c in single.data)
            or any(c.error for single in device_diff.values() for c in single.values())
            or any(c.error for single in gen_diff.values() for c in single)
            or any(c.error for c in cmds.values())
        )

    def _diff(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_res: dict[DeviceID, GenerationResult],
        filter_acl: dict[DeviceID, list[FilterAcl]],
    ) -> dict[DeviceID, dict[str | None, Diff]]:
        return {
            device.id: self._merger.diff(
                device, live_configs[device.id], gen_res[device.id].data, filter_acl.get(device.id, [])
            )
            for device in devices
            if not live_configs[device.id].error
            if not gen_res[device.id].error
        }

    def _gen_diff(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_res: dict[DeviceID, GenerationResult],
        filter_acl: dict[DeviceID, list[FilterAcl]],
    ) -> dict[DeviceID, list[ShowGenDiff]]:
        return {
            device.id: make_gen_diff(
                self._merger,
                device,
                live_configs[device.id],
                gen_res[device.id].data,
                filter_acl.get(device.id, []),
            )
            for device in devices
            if not live_configs[device.id].error
            if not gen_res[device.id].error
        }

    def _make_filter_acl(self, devices: list[Device]) -> dict[DeviceID, list[FilterAcl]]:
        return {device.id: self._filter_acl_src.filter_acl(device) for device in devices}

    async def handle(self, query: Any, timeout: timedelta | None) -> HandlerError | None:
        logger.info("Loading devices")
        devices = self._storage.make_devices(query)
        if not devices:
            logger.error("No devices found for query: %s", query)
            return HandlerError("No devices found")

        logger.info("Loading live configs")
        files = self._data_src.list_files(devices)
        live_configs = await self._fetcher.fetch(devices, files)

        logger.info("Apply initial configs")
        live_configs = self._apply_initial(devices, live_configs)

        logger.info("Preparing new configs")
        gen_res = self._data_src.generate(devices)

        logger.info("Prepare filter ACL")
        filter_acl = self._make_filter_acl(devices)

        logger.info("Preparing diff")
        diff = self._diff(devices, live_configs, gen_res, filter_acl)

        logger.info("Preparing generator diff")
        gen_diff = self._gen_diff(devices, live_configs, gen_res, filter_acl)

        logger.info("Generating commit message")
        commit_message = await self._commit_message_source.get_message()

        logger.info("Generating commands")
        if timeout:
            cmds = {
                device.id: self._merger.patch_trial(
                    device,
                    live_configs[device.id],
                    gen_res[device.id].data,
                    filter_acl.get(device.id, []),
                    commit_message,
                    timeout=timeout,
                )
                for device in devices
                if not live_configs[device.id].error
                if not gen_res[device.id].error
            }
            return await self._process_trial_diff(devices, live_configs, gen_res, diff, gen_diff, cmds, commit_message)

        cmds = {
            device.id: self._merger.patch(
                device,
                live_configs[device.id],
                gen_res[device.id].data,
                filter_acl.get(device.id, []),
                commit_message,
            )
            for device in devices
            if not live_configs[device.id].error
            if not gen_res[device.id].error
        }
        return await self._process_diff(devices, live_configs, gen_res, diff, gen_diff, cmds)

    @abstractmethod
    async def _process_diff(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        device_diff: dict[DeviceID, dict[str | None, Diff]],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
        cmds: dict[DeviceID, DeviceCommands],
    ) -> HandlerError | None:
        raise NotImplementedError

    @abstractmethod
    async def _process_trial_diff(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        device_diff: dict[DeviceID, dict[str | None, Diff]],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
        cmds: dict[DeviceID, DeviceCommands],
        commit_message: str,
    ) -> HandlerError | None:
        raise NotImplementedError


class CliDeploy(_CliDiffDeploy):
    def __init__(
        self,
        *,
        storage: Storage,
        fetcher: DeviceStateLoader,
        deployer_factory: DeviceDriverFactory,
        data_src: GeneratedDataSource,
        initial_data_src: GeneratedDataSource,
        filter_acl_src: FilterAclSource,
        merger: GeneratorMerger,
        deploy_ui: DeployUI,
        commander_registry: VendorCommanderRegistry,
        commit_message_source: CommitMessageSource,
        tolerate_fails: bool,
    ) -> None:
        super().__init__(
            storage=storage,
            fetcher=fetcher,
            data_src=data_src,
            merger=merger,
            initial_data_src=initial_data_src,
            filter_acl_src=filter_acl_src,
            commit_message_source=commit_message_source,
        )
        self._deployer_factory = deployer_factory
        self._deploy_ui = deploy_ui
        self._commander_registry = commander_registry
        self._tolerate_fails = tolerate_fails

    def _show_errors(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        device_diff: dict[DeviceID, dict[str | None, Diff]],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
        cmds: dict[DeviceID, DeviceCommands],
    ) -> HandlerError | None:
        logger.info("Checking errors")
        if self._has_gen_errors(live_configs, gen_data, device_diff, gen_diff, cmds) and not self._tolerate_fails:
            self._deploy_ui.show_errors(devices, live_configs, gen_data, device_diff, cmds, gen_diff)
            return HandlerError("Errors detected, cannot deploy")

        if all(cmd.is_empty() for cmd in cmds.values()) and (any(device_diff.values()) or any(gen_diff.values())):
            logger.info("No commands to show, but Diff found")
            logger.info("%s", device_diff)
            logger.info("%s", gen_diff)
            self._deploy_ui.show(devices, live_configs, gen_data, device_diff, cmds, gen_diff)
            return HandlerError("Diff found while there are no commands")
        return None

    def _quit_cmds(self, devices: list[Device]) -> dict[DeviceID, DeviceCommands]:
        return {device.id: self._commander_registry.match(device.hw).quit() for device in devices}

    async def _process_diff(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        device_diff: dict[DeviceID, dict[str | None, Diff]],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
        cmds: dict[DeviceID, DeviceCommands],
    ) -> HandlerError | None:
        logger.info("Checking errors")
        if err := self._show_errors(devices, live_configs, gen_data, device_diff, gen_diff, cmds):
            return err

        if all(cmd.is_empty() for cmd in cmds.values()):
            logger.info("No commands to show")
            return None

        logger.info("Show commands")
        logger.info("Deployer factory: %s", self._deployer_factory)
        if not self._deploy_ui.confirm_deployment(devices, live_configs, gen_data, device_diff, cmds, gen_diff):
            return None

        logger.info("Deploy")
        devices = [d for d in devices if d.id in cmds]
        async with self._deployer_factory.make_driver(devices, self._quit_cmds(devices)) as deployer:
            conn_errors = deployer.get_connection_errors(devices)
            if not self._tolerate_fails and conn_errors:
                return HandlerError("Connection errors detected")

            devices = [d for d in devices if d.id not in conn_errors]
            cmds = {did: cmds[did] for did in cmds if did not in conn_errors}
            async with self._deploy_ui.progress_bar(devices) as progressbar:
                result = await deployer.execute(devices, cmds, progressbar)

        deploy_result = self._parse_commit_result(devices, result)
        logger.info("Show report")
        self._deploy_ui.show_deploy_result(devices, deploy_result)

        if any(r.errors for r in deploy_result.values()):
            return HandlerError("Deploy failed")
        return None

    async def _process_trial_diff(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        device_diff: dict[DeviceID, dict[str | None, Diff]],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
        cmds: dict[DeviceID, DeviceCommands],
        commit_message: str,
    ) -> HandlerError | None:
        if err := self._show_errors(devices, live_configs, gen_data, device_diff, gen_diff, cmds):
            return err

        if all(cmd.is_empty() for cmd in cmds.values()):
            logger.info("No commands to show")
            return None

        logger.info("Show commands")
        logger.info("Deployer factory: %s", self._deployer_factory)
        if not self._deploy_ui.confirm_deployment(devices, live_configs, gen_data, device_diff, cmds, gen_diff):
            return None

        logger.info("Deploy with commit trial")
        async with self._deployer_factory.make_driver(devices, self._quit_cmds(devices)) as deployer:
            conn_errors = deployer.get_connection_errors(devices)
            if not self._tolerate_fails and conn_errors:
                return HandlerError("Connection errors detected")

            devices = [d for d in devices if d.id not in conn_errors]
            cmds = {did: cmds[did] for did in cmds if did not in conn_errors}

            async with self._deploy_ui.progress_bar(devices) as progressbar:
                result = await deployer.execute(devices, cmds, progressbar)

            deploy_result = self._parse_trial_deploy_result(devices, result)
            logger.info("Show report")
            self._deploy_ui.show_deploy_result(devices, deploy_result)

            if any(r.errors for r in deploy_result.values()):
                return HandlerError("Deploy failed")

            return await self._finalize_trial(deployer, devices, deploy_result, commit_message)

    async def _finalize_trial(
        self,
        deployer: DeviceDriver,
        devices: list[Device],
        deploy_result: dict[DeviceID, DeployResult],
        commit_message: str,
    ) -> HandlerError | None:
        logger.info("Ask confirmation")
        confirm_cmds = self._confirm_cmds(devices, deploy_result, commit_message)
        reset_cmds = self._reset_cmds(devices, deploy_result)
        confirm = self._deploy_ui.confirm_trial_confirmation(devices, confirm_cmds, reset_cmds)
        if confirm is TrialConfirmationAction.CONFIRM:
            return await self._confirm_trial(deployer, devices, confirm_cmds)
        if confirm is TrialConfirmationAction.ROLLBACK:
            return await self._reset_trial(deployer, devices, reset_cmds)
        return None

    def _confirm_cmds(
        self,
        devices: list[Device],
        deploy_results: dict[DeviceID, DeployResult],
        commit_message: str,
    ) -> dict[DeviceID, DeviceCommands]:
        cmds = {}
        for device in devices:
            commander = self._commander_registry.match(device.hw)
            trial_state = deploy_results[device.id].trial_state
            if trial_state is not None:
                cmds[device.id] = commander.confirm_trial(commit_message, trial_state)
        return cmds

    def _reset_cmds(
        self, devices: list[Device], deploy_results: dict[DeviceID, DeployResult]
    ) -> dict[DeviceID, DeviceCommands]:
        cmds = {}
        for device in devices:
            commander = self._commander_registry.match(device.hw)
            trial_state = deploy_results[device.id].trial_state
            if trial_state is not None:
                cmds[device.id] = commander.reset_trial(trial_state)
        return cmds

    async def _is_devices_available(self, devices: list[Device]) -> bool:
        async with self._deployer_factory.make_driver(devices, self._quit_cmds(devices)) as deployer:
            conn_errors = deployer.get_connection_errors(devices)
        return not conn_errors

    async def _confirm_trial(
        self,
        deployer: DeviceDriver,
        devices: list[Device],
        cmds: dict[DeviceID, DeviceCommands],
    ) -> HandlerError | None:
        if not await self._is_devices_available(devices):
            return HandlerError("Not all devices available, skip confirmation")

        async with self._deploy_ui.progress_bar(devices) as progressbar:
            result = await deployer.execute(devices, cmds, progressbar)

        deploy_result = self._parse_confirm_trial_result(devices, result)
        self._deploy_ui.show_deploy_result(devices, deploy_result)

        if any(r.errors for r in deploy_result.values()):
            return HandlerError("Confirm trial failed")
        return None

    async def _reset_trial(
        self,
        deployer: DeviceDriver,
        devices: list[Device],
        cmds: dict[DeviceID, DeviceCommands],
    ) -> HandlerError | None:
        async with self._deploy_ui.progress_bar(devices) as progressbar:
            result = await deployer.execute(devices, cmds, progressbar)

        deploy_result = self._parse_reset_trial_result(devices, result)
        self._deploy_ui.show_deploy_result(devices, deploy_result)

        if any(r.errors for r in deploy_result.values()):
            return HandlerError("Reset trial failed")
        return None

    def _parse_confirm_trial_result(
        self, devices: list[Device], result: dict[DeviceID, DeviceResult]
    ) -> dict[DeviceID, DeployResult]:
        res = {}
        for device in devices:
            device_res = result.get(device.id)
            if not device_res:
                continue

            if errors := device_res.all_errors:
                res[device.id] = DeployResult(errors=errors)
            else:
                commander = self._commander_registry.match(device.hw)
                res[device.id] = DeployResult(
                    commit_state=commander.parse_confirm_trial(device_res),
                )
        return res

    def _parse_commit_result(
        self, devices: list[Device], result: dict[DeviceID, DeviceResult]
    ) -> dict[DeviceID, DeployResult]:
        res = {}
        for device in devices:
            device_res = result.get(device.id)
            if not device_res:
                continue

            if errors := device_res.all_errors:
                res[device.id] = DeployResult(errors=errors)
            else:
                commander = self._commander_registry.match(device.hw)
                res[device.id] = DeployResult(
                    commit_state=commander.parse_commit(device_res),
                )
        return res

    def _parse_reset_trial_result(
        self, devices: list[Device], result: dict[DeviceID, DeviceResult]
    ) -> dict[DeviceID, DeployResult]:
        res = {}
        for device in devices:
            device_res = result.get(device.id)
            if not device_res:
                continue

            if errors := device_res.all_errors:
                res[device.id] = DeployResult(errors=errors)
            else:
                res[device.id] = DeployResult()
        return res

    def _parse_trial_deploy_result(
        self, devices: list[Device], result: dict[DeviceID, DeviceResult]
    ) -> dict[DeviceID, DeployResult]:
        res = {}
        for device in devices:
            device_res = result.get(device.id)
            if not device_res:
                continue

            if errors := device_res.all_errors:
                res[device.id] = DeployResult(errors=errors)
            else:
                commander = self._commander_registry.match(device.hw)
                res[device.id] = DeployResult(
                    trial_state=commander.parse_trial(device_res),
                )
        return res


class CliDiff(_CliDiffDeploy):
    def __init__(
        self,
        storage: Storage,
        fetcher: DeviceStateLoader,
        data_src: GeneratedDataSource,
        initial_data_src: GeneratedDataSource,
        filter_acl_src: FilterAclSource,
        merger: GeneratorMerger,
        diff_ui: DiffUI,
        commit_message_source: CommitMessageSource,
    ) -> None:
        super().__init__(
            storage=storage,
            fetcher=fetcher,
            data_src=data_src,
            merger=merger,
            initial_data_src=initial_data_src,
            filter_acl_src=filter_acl_src,
            commit_message_source=commit_message_source,
        )
        self._diff_ui = diff_ui

    async def _process_diff(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
        gen_data: dict[DeviceID, GenerationResult],
        device_diff: dict[DeviceID, dict[str | None, Diff]],
        gen_diff: dict[DeviceID, list[ShowGenDiff]],
        cmds: dict[DeviceID, DeviceCommands],
        commit_message: str = "",  # noqa: ARG002
    ) -> HandlerError | None:
        has_errors = self._has_gen_errors(live_configs, gen_data, device_diff, gen_diff, cmds)
        await self._diff_ui.show_diff(devices, live_configs, gen_data, device_diff, cmds, gen_diff, has_errors)
        if has_errors:
            return HandlerError("Errors detected")
        return None

    _process_trial_diff = _process_diff
