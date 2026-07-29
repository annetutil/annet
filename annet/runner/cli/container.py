from collections.abc import AsyncIterator
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime
from datetime import timezone
from pathlib import Path

from annet.cli_args import GenSelectOptions
from annet.diff import file_differ_connector
from annet.rulebook import rulebook_provider_connector
from annet.storage import Storage
from annet.storage import get_storage
from annet.vendors import registry_connector

from annet.commit.registry import VendorCommanderRegistryImpl
from annet.runner.cli.args import CommitOptions
from annet.runner.cli.args import DeploySourceOptions
from annet.runner.cli.args import FetcherOptions
from annet.runner.cli.args import FilterAclOptions
from annet.runner.cli.args import GenOutputOptions
from annet.runner.cli.args import OldGenOptions
from annet.runner.cli.args import ShowCurrentOutputOptions
from annet.runner.cli.args import ShowDeviceDumpOutputOptions
from annet.runner.cli.args import ShowGenOutputOptions
from annet.runner.cli.args import StorageOptions
from annet.runner.deploy_protocols import DeviceDriverFactory
from annet.runner.deploy_protocols import VendorCommanderRegistry
from annet.runner.protocols import CommitMessageSource
from annet.runner.protocols import DeviceStateLoader
from annet.runner.protocols import FilterAclSource
from annet.runner.protocols import GeneratedDataOutput
from annet.runner.protocols import GeneratedDataSource
from annet.runner.protocols import GeneratorMerger
from annet.runner.protocols import GeneratorSource
from annet.runner.protocols import ShowCurrentUI
from annet.runner.protocols import ShowDeviceUI
from annet.runner.protocols import ShowGenInfo
from annet.runner.services.commit_message import LocalUserCommitMessageSource
from annet.runner.services.fetch import DeviceDriverLoader
from annet.runner.services.file_filter_acl import FileFilterAcl
from annet.runner.services.file_filter_acl import StdinFilterAcl
from annet.runner.services.file_filter_acl import StubFilterAcl
from annet.runner.services.file_storage import LocalDeviceStateLoader
from annet.runner.services.find_gen import GeneratorsSourceImpl
from annet.runner.services.find_gen import InitialGeneratorSource
from annet.runner.services.gen_data_storage import StoredDataOutput
from annet.runner.services.gen_data_storage import StoredDataSource
from annet.runner.services.generate import GeneratingSource
from annet.runner.services.gnetcli_adapter import GnetCliDriverFactory
from annet.runner.services.merger_all import AllGeneratorMerger
from annet.runner.services.merger_all import GeneratedStateLoader
from annet.runner.services.merger_cli import CliConfigMerger
from annet.runner.services.merger_files import FilesMerger
from annet.runner.services.merger_json import JsonFilesMerger
from annet.runner.ui import show_gen as show_gen_ui
from annet.runner.ui.gen import ConsoleDataOutput
from annet.runner.ui.show_current import ConsoleShowCurrent
from annet.runner.ui.show_current import StoreCurrent
from annet.runner.ui.show_devices import ConsoleShowDevice
from annet.runner.ui.show_devices import StoreDevice
from gnetcli_adapter import gnetcli_adapter

start_time = datetime.now(tz=timezone.utc).astimezone()


def make_storage(args: StorageOptions) -> Storage:
    connector, conf_params = get_storage()
    storage_opts = connector.opts().parse_params(conf_params, args)
    return connector.storage()(storage_opts)


def make_gen_output(args: GenOutputOptions) -> GeneratedDataOutput:
    if args.dest:
        return StoredDataOutput(Path(args.dest), not args.no_clear)
    return ConsoleDataOutput(per_gen=args.per_gen)


def make_gen_source(
    storage: Storage,
    args: GenSelectOptions,
) -> GeneratorSource:
    return GeneratorsSourceImpl(
        storage=storage,
        gen_select_options=args,
    )


def make_generated_src(storage: Storage, args: GenSelectOptions) -> GeneratedDataSource:
    return GeneratingSource(
        storage=storage,
        generators_source=make_gen_source(storage, args),
        vendor_registry=registry_connector.get(),
        rulebook_provider=rulebook_provider_connector.get(),
    )


def make_init_data_src(storage: Storage) -> GeneratedDataSource:
    return GeneratingSource(
        storage=storage,
        generators_source=InitialGeneratorSource(storage),
        vendor_registry=registry_connector.get(),
        rulebook_provider=rulebook_provider_connector.get(),
    )


def make_src(
    storage: Storage,
    generator_args: GenSelectOptions,
    deploy_src_args: DeploySourceOptions,
) -> GeneratedDataSource:
    if deploy_src_args.input:
        return StoredDataSource(Path(deploy_src_args.input), generator_args)
    return make_generated_src(storage, generator_args)


def make_generated_fetcher(
    generator_args: GenSelectOptions,
    old_generator_args: OldGenOptions,
) -> DeviceStateLoader:
    data_src = StoredDataSource(Path(old_generator_args.old_data_dir), generator_args)
    merger = make_merger()
    return GeneratedStateLoader(data_src, merger)


def make_device_driver_factory() -> DeviceDriverFactory:
    # TODO read context:
    return GnetCliDriverFactory(
        logs_dir="",
        settings=gnetcli_adapter.AppSettings(),
        start_time=start_time,
    )


def make_commander_registry() -> VendorCommanderRegistry:
    return VendorCommanderRegistryImpl()


def make_fetcher(
    deploy_src_args: FetcherOptions,
) -> DeviceStateLoader:
    if deploy_src_args.config_dir:
        config_dir = Path(deploy_src_args.config_dir)
        return LocalDeviceStateLoader(config_dir)

    return DeviceDriverLoader(
        driver=make_device_driver_factory(),
        commander_registry=make_commander_registry(),
    )


def make_merger() -> GeneratorMerger:
    cli_merger = CliConfigMerger(
        vendor_registry=registry_connector.get(),
        rulebook_provider=rulebook_provider_connector.get(),
        vendor_commander_registry=make_commander_registry(),
    )
    files_merger = FilesMerger(
        rulebook_provider=rulebook_provider_connector.get(),
        file_differ=file_differ_connector.get(),
    )
    json_files_merger = JsonFilesMerger(
        rulebook_provider=rulebook_provider_connector.get(),
        file_differ=file_differ_connector.get(),
    )
    return AllGeneratorMerger(
        file_mergers={
            None: cli_merger,
        },
        default_merger=files_merger,
        default_json_merger=json_files_merger,
        vendor_registry=registry_connector.get(),
        vendor_commander_registry=make_commander_registry(),
    )


def make_show_gen_output(args: ShowGenOutputOptions) -> Callable[[list[ShowGenInfo]], None]:
    if args.format == "text":
        return show_gen_ui.print_text
    if args.format == "json":
        return show_gen_ui.print_json

    msg = f"Unsupported format: {args.format}"
    raise ValueError(msg)


def make_show_current_output(args: ShowCurrentOutputOptions) -> ShowCurrentUI:
    if args.dest:
        return StoreCurrent(Path(args.dest))
    return ConsoleShowCurrent()


def make_show_device_dump_output(args: ShowDeviceDumpOutputOptions) -> ShowDeviceUI:
    if args.dest:
        return StoreDevice(Path(args.dest))
    return ConsoleShowDevice()


def make_filter_acl_source(args: FilterAclOptions) -> FilterAclSource:
    if args.filter_acl == "-":
        return StdinFilterAcl()
    if args.filter_acl:
        return FileFilterAcl(args.filter_acl)
    return StubFilterAcl()


@asynccontextmanager
async def make_commit_message_source(args: CommitOptions) -> AsyncIterator[CommitMessageSource]:
    yield LocalUserCommitMessageSource(args.message)
