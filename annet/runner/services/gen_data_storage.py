import logging
import shutil
import urllib.parse
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import TypeVar

import yaml
from adaptix import Retort
from annet.cli_args import GenSelectOptions
from annet.generators import DISABLED_TAG
from annet.storage import Device

from annet.runner.deploy_protocols import DeviceConfig
from annet.runner.protocols import DeviceID
from annet.runner.protocols import GeneratedData
from annet.runner.protocols import GeneratedDataOutput
from annet.runner.protocols import GeneratedDataSource
from annet.runner.protocols import GenerationResult

logger = logging.getLogger(__name__)


def _str_presenter(dumper: yaml.representer.BaseRepresenter, data: str) -> yaml.ScalarNode:
    if "\n" in data:
        return dumper.represent_scalar(
            "tag:yaml.org,2002:str",
            data,
            style="|",
        )
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, _str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, _str_presenter)


@dataclass
class StoredGeneratorInfo:
    name: str
    tags: list[str]
    aliases: list[str]

    path: str | None
    acl_path: str | None
    data_path: str | None

    priority: int | None
    before_cmds: str | None
    after_cmds: str | None

    error: str | None


@dataclass
class DeviceGeneratorInfo:
    generators: list[StoredGeneratorInfo]
    error: str | None = None


retort = Retort()
INFO_FILE_NAME = "_generators.yaml"


def get_device_path(device: Device, path: Path) -> Path:
    name = urllib.parse.quote(device.fqdn, safe="")
    return path / name


class StoredDataOutput(GeneratedDataOutput):
    def __init__(self, path: Path, clear_dir: bool = True) -> None:
        """
        :param path: Local path to store generated data.
        :param clear_dir: Clear the generated data directory before storing data.
                          Specific device dirs will be recreated anyway.
        """
        self._path = path
        self._clear_dir: bool = clear_dir

    def _save_info(
        self,
        result: GeneratedData,
        path: Path,
    ) -> StoredGeneratorInfo:
        output_path: Path | None
        if result.path:  # noqa: SIM108
            output_path = path / Path(result.path).relative_to("/")
        else:
            output_path = path / result.name
        if output_path.exists():
            for i in count():
                tmp_path = output_path.parent / f"{output_path.name}_{i}"
                if not tmp_path.exists():
                    output_path = tmp_path
                    break
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if result.acl:
            acl_path = output_path.parent / f"{output_path.name}.acl"
            acl_path.write_text(result.acl)
        else:
            acl_path = None

        if result.output is not None:
            output_path.write_text(result.output)
        else:
            output_path = None
        return StoredGeneratorInfo(
            name=result.name,
            tags=sorted(result.tags),
            aliases=sorted(result.aliases),
            path=result.path,
            data_path=str(output_path.relative_to(path)) if output_path else None,
            acl_path=str(acl_path.relative_to(path)) if acl_path else None,
            priority=result.priority,
            before_cmds=result.before_cmds,
            after_cmds=result.after_cmds,
            error=result.error,
        )

    def _save_device_results(
        self,
        device: Device,
        result: GenerationResult,
        path: Path,
    ) -> None:
        path = get_device_path(device, path)
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)

        saved_info = [self._save_info(path=path, result=single_res) for single_res in result.data]
        saved_info.sort(key=lambda x: x.name)
        stored_result = DeviceGeneratorInfo(generators=saved_info, error=result.error)
        device_path = path / INFO_FILE_NAME
        data = retort.dump(stored_result, DeviceGeneratorInfo)
        with device_path.open(mode="w") as file:
            yaml.safe_dump(data, file)

    async def print(
        self,
        devices: list[Device],
        generators_results: dict[DeviceID, GenerationResult],
        results: dict[DeviceID, DeviceConfig],  # noqa: ARG002
    ) -> None:
        logger.info("Printing generated data to file %r", str(self._path))
        if self._path.is_dir() and self._clear_dir:
            shutil.rmtree(self._path)
        self._path.mkdir(parents=True, exist_ok=True)
        for device in devices:
            self._save_device_results(
                device=device,
                result=generators_results[device.id],
                path=self._path,
            )


T = TypeVar("T", bound=StoredGeneratorInfo)


def select_generators(gens: GenSelectOptions, genresult: Iterable[T]) -> list[T]:
    def contains(obj: T, where: set[str]) -> bool:
        if where:
            return bool(set(obj.aliases).intersection(where))
        return False

    def has(cls: T, what: str) -> bool:
        return what in cls.tags

    flts = []
    if gens.allowed_gens:
        flts.append(lambda c: contains(c, gens.allowed_gens))
    elif gens.force_enabled:
        flts.append(
            lambda c: not has(c, DISABLED_TAG) or contains(c, gens.force_enabled),
        )
    elif not gens.ignore_disabled:
        flts.append(lambda c: not has(c, DISABLED_TAG))

    if gens.excluded_gens:
        flts.append(lambda c: not contains(c, gens.excluded_gens))

    return list(filter(lambda x: all(f(x) for f in flts), genresult))


class StoredDataSource(GeneratedDataSource):
    def __init__(self, path: Path, gen_select_options: GenSelectOptions) -> None:
        self._path = path
        self._gen_select_options = gen_select_options

    def _load_device_info(self, path: Path) -> DeviceGeneratorInfo:
        path = path / INFO_FILE_NAME
        if not path.exists():
            return DeviceGeneratorInfo(generators=[], error="File not found")
        with path.open("r") as file:
            data = yaml.safe_load(file)
        return retort.load(data, DeviceGeneratorInfo)

    def _load_device_results(
        self,
        path: Path,
        device: Device,
    ) -> GenerationResult:
        path = get_device_path(device, path)
        if not path.exists():
            return GenerationResult(error="File not found")
        info = self._load_device_info(path=path)
        info.generators = select_generators(self._gen_select_options, info.generators)
        return GenerationResult(
            data=[
                GeneratedData(
                    path=gen_info.path,
                    priority=gen_info.priority,
                    before_cmds=gen_info.before_cmds,
                    after_cmds=gen_info.after_cmds,
                    name=gen_info.name,
                    tags=gen_info.tags,
                    aliases=gen_info.aliases,
                    output=(path / gen_info.data_path).read_text() if gen_info.data_path else None,
                    acl=(path / gen_info.acl_path).read_text() if gen_info.acl_path else None,
                    error=gen_info.error,
                )
                for gen_info in info.generators
            ]
        )

    def generate(self, devices: list[Device]) -> dict[DeviceID, GenerationResult]:
        logger.info("Loading generated data from file %r", str(self._path))
        return {device.id: self._load_device_results(self._path, device) for device in devices}

    def list_files(self, devices: list[Device]) -> dict[DeviceID, list[str]]:
        res = {}
        for device in devices:
            info = self._load_device_info(path=get_device_path(device, self._path))
            if info:
                res[device.id] = [data.path for data in info.generators if data.path]

        return res
