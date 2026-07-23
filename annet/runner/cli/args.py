from datetime import timedelta

from annet.argparse import Arg
from annet.argparse import ArgGroup
from annet.cli_args import opt_query_factory


class GenOutputOptions(ArgGroup):
    dest: str = Arg(
        "--dest",
        default="",
        help="Output destination directory",
    )
    per_gen: bool = Arg(
        "--per-gen",
        default=False,
        help="Show changes per generator",
    )
    no_clear: bool = Arg(
        "--no-clear",
        default=False,
        help="Do not clear the dest directory before generating",
    )


class ShowGenOutputOptions(ArgGroup):
    format: str = Arg(
        "--format",
        default="text",
        choices=["text", "json"],
        help="Output format",
    )


class ShowCurrentOutputOptions(ArgGroup):
    dest: str = Arg(
        "--dest",
        default="",
        help="Output destination directory",
    )


class ShowDeviceDumpOutputOptions(ArgGroup):
    dest: str = Arg(
        "--dest",
        default="",
        help="Output destination directory",
    )


class QueryOptions(ArgGroup):
    query: list[str] = opt_query_factory(nargs="+")


class OptionalQueryOptions(ArgGroup):
    query: list[str] = opt_query_factory(nargs="*")


class DeploySourceOptions(ArgGroup):
    input: str = Arg(
        "--input-dir",
        default="",
        help="Generator data directory",
    )


class CommitOptions(ArgGroup):
    trial: bool = Arg(
        "--trial",
        default=False,
        action="store_true",
        help="Enable commit-trial mode",
    )
    trial_timeout: timedelta = Arg(
        "--trial-timeout",
        type=lambda seconds: timedelta(seconds=int(seconds)),
        default=timedelta(seconds=60),
        help="Enable commit-trial mode",
    )
    message: str = Arg("--message", type=str, default="", help="Commit message")


class DeployUIOptions(ArgGroup):
    no_ask_deploy: bool = Arg(
        "--no-ask-deploy",
        default=False,
        help="Autoconfirm deployment",
    )
    auto_confirm_trial: timedelta = Arg(
        "--trial-auto-confirm",
        type=lambda seconds: timedelta(seconds=int(seconds)),
        default=None,
        help="Pause before automatic confirmation of commit trial",
    )
    no_progress: bool = Arg(
        "--no-progress",
        default=False,
        help="Hide progress bar",
    )


class FetcherOptions(ArgGroup):
    config_dir: str = Arg(
        "--config",
        default=None,
        help="Device state directory",
    )


class OldGenOptions(ArgGroup):
    old_data_dir: str = Arg(
        "--old-data-dir",
        help="Old generator data directory",
    )


class DiffUiOptions(ArgGroup):
    per_gen: bool = Arg(
        "--per-gen",
        default=False,
        help="Show changes per generator",
    )


class FilterAclOptions(ArgGroup):
    filter_acl: str = Arg(
        "--filter-acl",
        default="",
        help="Path to a directory containing filter acls",
    )


class StorageOptions(ArgGroup):
    recache: bool = Arg("--recache", default=False, help="Force expiration of storage's local cache if it is supported")
