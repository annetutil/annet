import logging
import traceback
from collections import defaultdict
from collections.abc import Sequence
from datetime import timedelta

from annet.storage import Device
from annet.vendors import Registry

from annet.runner.deploy_protocols import DeviceCommands
from annet.runner.deploy_protocols import DeviceConfig
from annet.runner.deploy_protocols import VendorCommanderRegistry
from annet.runner.protocols import DeviceID
from annet.runner.protocols import DeviceStateLoader
from annet.runner.protocols import Diff
from annet.runner.protocols import FilterAcl
from annet.runner.protocols import GeneratedData
from annet.runner.protocols import GeneratedDataSource
from annet.runner.protocols import GeneratorMerger
from annet.runner.services.cmds import unite_commands

logger = logging.getLogger(__name__)


class AllGeneratorMerger(GeneratorMerger):
    def __init__(
        self,
        file_mergers: dict[str | None, GeneratorMerger],
        default_merger: GeneratorMerger,
        default_json_merger: GeneratorMerger,
        vendor_registry: Registry,
        vendor_commander_registry: VendorCommanderRegistry,
    ) -> None:
        self._file_mergers = file_mergers
        self._default_merger = default_merger
        self._default_json_merger = default_json_merger
        self._vendor_registry = vendor_registry
        self._vendor_commander_registry = vendor_commander_registry

    def _get_merger(self, gen_data: GeneratedData) -> GeneratorMerger:
        if gen_data.path in self._file_mergers:
            return self._file_mergers[gen_data.path]
        if gen_data.is_json:
            return self._default_json_merger
        return self._default_merger

    def _group_data(
        self,
        gen_data: Sequence[GeneratedData],
    ) -> dict[str | None, list[GeneratedData]]:
        gen_data = sorted(gen_data, key=lambda g: (g.priority is None, g.priority), reverse=True)
        files_gens = defaultdict(list)
        for single_gen_data in gen_data:
            files_gens[single_gen_data.path].append(single_gen_data)

        for path, data in files_gens.items():
            json_count = sum(1 for d in data if d.is_json)
            if json_count != len(data) and json_count != 0:
                generator_names = ", ".join([d.name for d in data])
                message = (
                    f"Cannot mix JSONFragment and Entire/Partial generators for {path},"
                    f" found generators: {generator_names}"
                )
                raise ValueError(message)
        files_gens.default_factory = None
        return files_gens

    def diff(
        self,
        device: Device,
        live_config: DeviceConfig,
        gen_data: Sequence[GeneratedData],
        filter_acl: list[FilterAcl],
    ) -> dict[str | None, Diff]:
        res: dict[str | None, Diff] = {}
        if any(x.error for x in gen_data):
            logger.warning("Found errors for %s, skipping diff logic", device.fqdn)
            return res
        for file, data in self._group_data(gen_data).items():
            merger = self._get_merger(data[0])
            try:
                res |= merger.diff(device, live_config, data, filter_acl)
            except Exception:  # noqa: BLE001
                res[file] = Diff(diff="", error=traceback.format_exc(), path=file)
        return res

    def patch(
        self,
        device: Device,
        live_config: DeviceConfig,
        gen_data: Sequence[GeneratedData],
        filter_acl: list[FilterAcl],
        commit_message: str,
    ) -> DeviceCommands:
        res = DeviceCommands()
        if any(x.error for x in gen_data):
            logger.info("Found errors for %s, skipping patch logic", device.fqdn)
            return res
        for data in self._group_data(gen_data).values():
            merger = self._get_merger(data[0])
            res = unite_commands(
                res,
                merger.patch(device, live_config, data, filter_acl, commit_message),
            )
        if not res.is_empty():
            commander = self._vendor_commander_registry.match(device.hw)
            res = unite_commands(res, commander.apply_commit_device(device, commit_message))
        return res

    def patch_trial(
        self,
        device: Device,
        live_config: DeviceConfig,
        gen_data: Sequence[GeneratedData],
        filter_acl: list[FilterAcl],
        commit_message: str,
        timeout: timedelta,
    ) -> DeviceCommands:
        res = DeviceCommands()
        if any(x.error for x in gen_data):
            logger.info("Found errors for %s, skipping patch logic", device.fqdn)
            return res
        for data in self._group_data(gen_data).values():
            merger = self._get_merger(data[0])
            res = unite_commands(
                res,
                merger.patch_trial(device, live_config, data, filter_acl, commit_message, timeout),
            )
        if not res.is_empty():
            commander = self._vendor_commander_registry.match(device.hw)
            res = unite_commands(res, commander.apply_trial_device(device, commit_message, timeout))
        return res

    def _unite_device_config(
        self,
        first: DeviceConfig,
        second: DeviceConfig,
    ) -> DeviceConfig:
        if first.config and second.config:
            msg = "Multiple device configs retrieved from different generator groups, cannot merge"
            raise ValueError(msg)
        if common_files := first.files.keys() & second.files.keys():
            msg = f"Files {common_files} retrieved from different generator groups, cannot merge"
            raise ValueError(msg)
        return DeviceConfig(
            config=first.config or second.config,
            files=first.files | second.files,
        )

    def make_device_config(
        self,
        device: Device,
        gen_data: Sequence[GeneratedData],
    ) -> DeviceConfig:
        res = DeviceConfig(config=None, files={})
        if any(x.error for x in gen_data):
            logger.info("Found errors for %s, skipping make device config logic", device.fqdn)
            res.error = "\n".join(str(x.error) for x in gen_data) or None
            return res
        for data in self._group_data(gen_data).values():
            merger = self._get_merger(data[0])
            res = self._unite_device_config(
                res,
                merger.make_device_config(device, data),
            )
        return res


class GeneratedStateLoader(DeviceStateLoader):
    def __init__(self, data_source: GeneratedDataSource, merger: GeneratorMerger) -> None:
        self._data_source = data_source
        self._merger = merger

    async def fetch(self, devices: list[Device], files: dict[DeviceID, list[str]]) -> dict[DeviceID, DeviceConfig]:
        gen_data = self._data_source.generate(devices)

        res = {}
        for device in devices:
            device_data = gen_data[device.id]
            if device_data.error:
                res[device.id] = DeviceConfig(error=device_data.error)
            else:
                cfg = self._merger.make_device_config(device, device_data.data)
                res[device.id] = DeviceConfig(
                    config=cfg.config, files={name: cfg.files.get(name, "") for name in files.get(device.id, [])}
                )
        return res
