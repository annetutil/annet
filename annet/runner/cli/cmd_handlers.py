import asyncio
import functools
import sys
from collections.abc import Callable
from collections.abc import Coroutine
from typing import TypeVar

from annet.argparse import Arg
from annet.argparse import subcommand
from annet.cli_args import GenSelectOptions

from annet.runner.protocols import HandlerError
from annet.runner.services.commit_message import SimpleCommitMessageSource
from annet.runner.ui.deploy import ConsoleDeployUI
from annet.runner.ui.deploy import ConsoleDiffUI
from annet.runner.ui.deploy import ConsolePatchUI
from annet.runner.ui.deploy import ConsoleRollbackShowUI
from annet.runner.usecase.deploy import CliDeploy
from annet.runner.usecase.deploy import CliDiff
from annet.runner.usecase.gen import CliGenerate
from annet.runner.usecase.show_current import CliShowCurrent
from annet.runner.usecase.show_device_dump import CliShowDeviceDump
from annet.runner.usecase.show_gen import CliShowGenerators
from annet.runner.usecase.show_rollback import CliShowRollback

from .args import CommitOptions
from .args import DeploySourceOptions
from .args import DeployUIOptions
from .args import DiffUiOptions
from .args import FetcherOptions
from .args import FilterAclOptions
from .args import GenOutputOptions
from .args import OldGenOptions
from .args import OptionalQueryOptions
from .args import QueryOptions
from .args import ShowCurrentOutputOptions
from .args import ShowDeviceDumpOutputOptions
from .args import ShowGenOutputOptions
from .args import StorageOptions
from .container import make_commander_registry
from .container import make_commit_message_source
from .container import make_device_driver_factory
from .container import make_fetcher
from .container import make_filter_acl_source
from .container import make_gen_output
from .container import make_gen_source
from .container import make_generated_fetcher
from .container import make_generated_src
from .container import make_init_data_src
from .container import make_merger
from .container import make_show_current_output
from .container import make_show_device_dump_output
from .container import make_show_gen_output
from .container import make_src
from .container import make_storage


class GenOptions(GenSelectOptions, GenOutputOptions, QueryOptions, StorageOptions):
    pass


ArgT = TypeVar("ArgT")
ResT = TypeVar("ResT")


def async_to_sync(func: Callable[[ArgT], Coroutine[None, None, ResT]]) -> Callable[[ArgT], ResT]:
    @functools.wraps(func)
    def wrapper(arg: ArgT) -> ResT:
        return asyncio.run(func(arg))

    return wrapper


@subcommand(is_group=True)
def show() -> None:
    """A group of commands for showing parameters/configurations/data from deivces and data sources"""
    pass


@subcommand(GenOptions)
@async_to_sync
async def gen(args: GenOptions) -> HandlerError | None:
    storage = make_storage(args)
    merger = make_merger()
    cli_generate = CliGenerate(
        storage=storage,
        data_src=make_generated_src(storage, args),
        output=make_gen_output(args),
        merger=merger,
    )
    return await cli_generate.handle(query=args.query)


class ShowGenOptions(GenSelectOptions, ShowGenOutputOptions, OptionalQueryOptions, StorageOptions):
    pass


@subcommand(ShowGenOptions, parent=show)
def show_gen(args: ShowGenOptions) -> HandlerError | None:
    storage = make_storage(args)
    cli_show_gen = CliShowGenerators(
        storage=storage,
        gen_src=make_gen_source(storage, args),
        output=make_show_gen_output(args),
    )
    return cli_show_gen.handle(query=args.query)


class ShowCurrentOptions(
    FetcherOptions,
    GenSelectOptions,
    ShowCurrentOutputOptions,
    QueryOptions,
    StorageOptions,
    DeploySourceOptions,
):
    pass


@subcommand(ShowCurrentOptions, parent=show)
@async_to_sync
async def show_current(args: ShowCurrentOptions) -> HandlerError | None:
    storage = make_storage(args)
    cli_show_current = CliShowCurrent(
        storage=storage,
        output=make_show_current_output(args),
        data_src=make_src(storage, generator_args=args, deploy_src_args=args),
        fetcher=make_fetcher(args),
    )
    return await cli_show_current.handle(args.query)


class ShowDeviceDumpOptions(
    QueryOptions,
    StorageOptions,
    ShowDeviceDumpOutputOptions,
):
    pass


@subcommand(ShowDeviceDumpOptions, parent=show)
@async_to_sync
async def show_device_dump(args: ShowDeviceDumpOptions) -> HandlerError | None:
    storage = make_storage(args)
    cli_show_device_dump = CliShowDeviceDump(
        storage=storage,
        output=make_show_device_dump_output(args),
    )
    return await cli_show_device_dump.handle(args.query)


class DeployOptions(
    GenSelectOptions,
    QueryOptions,
    GenOutputOptions,
    DeploySourceOptions,
    CommitOptions,
    FetcherOptions,
    DeployUIOptions,
    StorageOptions,
    FilterAclOptions,
):
    tolerate_fails: bool = Arg(
        "--tolerate-fails",
        default=False,
    )


@subcommand(DeployOptions)
@async_to_sync
async def deploy(args: DeployOptions) -> HandlerError | None:
    if not sys.stdout.isatty():
        args.no_progress = True

    storage = make_storage(args)
    async with make_commit_message_source(args) as commit_message_source:
        cli_deploy = CliDeploy(
            storage=storage,
            data_src=make_src(storage, generator_args=args, deploy_src_args=args),
            fetcher=make_fetcher(args),
            initial_data_src=make_init_data_src(storage),
            deployer_factory=make_device_driver_factory(),
            merger=make_merger(),
            deploy_ui=ConsoleDeployUI(
                no_progress=args.no_progress,
                deploy_auto_confirmation=True if args.no_ask_deploy else None,
                auto_confirm_trial=args.auto_confirm_trial,
            ),
            commander_registry=make_commander_registry(),
            tolerate_fails=args.tolerate_fails,
            filter_acl_src=make_filter_acl_source(args),
            commit_message_source=commit_message_source,
        )
        return await cli_deploy.handle(
            query=args.query,
            timeout=args.trial_timeout if args.trial else None,
        )


class DiffOptions(
    GenSelectOptions,
    QueryOptions,
    DeploySourceOptions,
    FetcherOptions,
    StorageOptions,
    DiffUiOptions,
    FilterAclOptions,
):
    pass


@subcommand(DiffOptions)
@async_to_sync
async def diff(args: DiffOptions) -> HandlerError | None:
    """
    Diff with devices state
    """
    storage = make_storage(args)
    cli_deploy = CliDiff(
        storage=storage,
        data_src=make_src(storage, generator_args=args, deploy_src_args=args),
        fetcher=make_fetcher(args),
        initial_data_src=make_init_data_src(storage),
        merger=make_merger(),
        diff_ui=ConsoleDiffUI(per_gen=args.per_gen),
        filter_acl_src=make_filter_acl_source(args),
        commit_message_source=SimpleCommitMessageSource(""),
    )
    return await cli_deploy.handle(
        query=args.query,
        timeout=None,
    )


class PatchOptions(
    GenSelectOptions,
    QueryOptions,
    DeploySourceOptions,
    CommitOptions,
    FetcherOptions,
    StorageOptions,
    FilterAclOptions,
):
    pass


@subcommand(PatchOptions)
@async_to_sync
async def patch(args: PatchOptions) -> HandlerError | None:
    """
    Patch based on diff with devices state
    """
    storage = make_storage(args)
    async with make_commit_message_source(args) as commit_message_source:
        cli_deploy = CliDiff(
            storage=storage,
            data_src=make_src(storage, generator_args=args, deploy_src_args=args),
            fetcher=make_fetcher(args),
            initial_data_src=make_init_data_src(storage),
            merger=make_merger(),
            diff_ui=ConsolePatchUI(),
            filter_acl_src=make_filter_acl_source(args),
            commit_message_source=commit_message_source,
        )
        return await cli_deploy.handle(
            query=args.query,
            timeout=args.trial_timeout if args.trial else None,
        )


class ShowRollbackOptions(
    QueryOptions,
    FetcherOptions,
    StorageOptions,
):
    pass


@subcommand(ShowRollbackOptions, parent=show)
@async_to_sync
async def show_rollback(args: ShowRollbackOptions) -> HandlerError | None:
    """
    Prepare commands for rollback to current state
    """
    storage = make_storage(args)
    cli_rollback = CliShowRollback(
        storage=storage,
        fetcher=make_fetcher(args),
        commander_registry=make_commander_registry(),
        output=ConsoleRollbackShowUI(),
    )
    return await cli_rollback.handle(query=args.query)


class GenDiffOptions(
    GenSelectOptions,
    QueryOptions,
    DeploySourceOptions,
    OldGenOptions,
    StorageOptions,
    DiffUiOptions,
    FilterAclOptions,
):
    pass


@subcommand(GenDiffOptions)
@async_to_sync
async def gen_diff(args: GenDiffOptions) -> HandlerError | None:
    """
    Diff with previous geenrators output
    """
    storage = make_storage(args)
    cli_deploy = CliDiff(
        storage=storage,
        data_src=make_src(storage, generator_args=args, deploy_src_args=args),
        fetcher=make_generated_fetcher(generator_args=args, old_generator_args=args),
        initial_data_src=make_init_data_src(storage),
        merger=make_merger(),
        diff_ui=ConsoleDiffUI(per_gen=args.per_gen),
        filter_acl_src=make_filter_acl_source(args),
        commit_message_source=SimpleCommitMessageSource(""),
    )
    return await cli_deploy.handle(
        query=args.query,
        timeout=None,
    )
