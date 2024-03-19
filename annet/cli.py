import argparse
import operator
import os
import platform
import subprocess
import shutil
from contextlib import ExitStack, contextmanager
from typing import Tuple, Iterable

import yaml
from contextlog import get_logger
from valkit.python import valid_logging_level

from annet.deploy import driver_connector, fetcher_connector
from annet import api, cli_args, filtering
from annet.api import collapse_texts, Deployer
from annet.argparse import ArgParser, subcommand
from annet.diff import gen_sort_diff
from annet.gen import Loader, old_raw
from annet.lib import get_context_path, repair_context_file
from annet.output import output_driver_connector, OutputDriver
from annet.storage import storage_connector


def fill_base_args(parser: ArgParser, pkg_name: str, logging_config: str):
    parser.add_argument("--log-level", default="WARN", type=valid_logging_level,
                        help="Уровень детализации логов (DEBUG, DEBUG2 (with comocutor debug), INFO, WARN, CRITICAL)")
    parser.add_argument("--pkg_name", default=pkg_name, help=argparse.SUPPRESS)
    parser.add_argument("--logging_config", default=logging_config, help=argparse.SUPPRESS)


def list_subcommands():
    return globals().copy()


def _gen_current_items(
        config,
        stdin,
        loader: Loader,
        output_driver: OutputDriver,
        gen_args: cli_args.GenOptions,
) -> Iterable[Tuple[str, str, bool]]:
    for device, result in old_raw(
        args=gen_args,
        loader=loader,
        config=config,
        stdin=stdin,
        do_files_download=True,
        use_mesh=False,
    ):
        if device.hw.vendor != "pc":
            destname = output_driver.cfg_file_names(device)[0]
            yield (destname, result, False)
        else:
            for entire_path, entire_data in sorted(result.items(), key=operator.itemgetter(0)):
                if entire_data is None:
                    entire_data = ""
                destname = output_driver.entire_config_dest_path(device, entire_path)
                yield (destname, entire_data, False)


@contextmanager
def get_loader(gen_args: cli_args.GenOptions, args: cli_args.QueryOptions):
    exit_stack = ExitStack()
    connectors = storage_connector.get_all()
    storages = []
    with exit_stack:
        for connector in connectors:
            storage_opts = connector.opts().from_cli_opts(args)
            storages.append(exit_stack.enter_context(connector.storage()(storage_opts)))
        yield Loader(*storages, args=gen_args)


@subcommand(cli_args.QueryOptions, cli_args.opt_config, cli_args.FileOutOptions)
def show_current(args: cli_args.QueryOptions, config, arg_out: cli_args.FileOutOptions) -> None:
    """ Показать текущий конфиг устройств """
    gen_args = cli_args.GenOptions(args, no_acl=True)
    output_driver = output_driver_connector.get()
    with get_loader(gen_args, args) as loader:
        if not loader.devices:
            get_logger().error("No devices found for %s", args.query)

        items = _gen_current_items(
            loader=loader,
            output_driver=output_driver,
            gen_args=gen_args,
            stdin=args.stdin(config=config),
            config=config,
        )
        output_driver.write_output(arg_out, items, len(loader.devices))


@subcommand(cli_args.ShowGenOptions)
def gen(args: cli_args.ShowGenOptions):
    """ Сгенерировать конфиг для устройств """
    with get_loader(args, args) as loader:
        (success, fail) = api.gen(args, loader)

        out = [item for items in success.values() for item in items]
        output_driver = output_driver_connector.get()
        if args.dest is None:
            text_mapping = {item[0]: item[1] for item in out}
            out = [(",".join(key), value, False) for key, value in collapse_texts(text_mapping).items()]

        out.extend(output_driver.format_fails(fail, loader.device_fqdns))
        total = len(success) + len(fail)
        if not total:
            get_logger().error("No devices found for %s", args.query)
        output_driver.write_output(args, out, total)


@subcommand(cli_args.ShowDiffOptions)
def diff(args: cli_args.ShowDiffOptions):
    """ Сгенерировать конфиг для устройств и показать дифф по рулбуку с текущим """
    with get_loader(args, args) as loader:
        filterer = filtering.filterer_connector.get()
        device_ids = loader.device_ids
        output_driver_connector.get().write_output(
            args,
            gen_sort_diff(api.diff(args, loader, device_ids, filterer), args),
            len(loader.device_ids)
        )


@subcommand(cli_args.ShowPatchOptions)
def patch(args: cli_args.ShowPatchOptions):
    """ Сгенерировать конфиг для устройств и сформировать патч """
    with get_loader(args, args) as loader:
        (success, fail) = api.patch(args, loader)

        out = [item for items in success.values() for item in items]
        output_driver = output_driver_connector.get()
        out.extend(output_driver.format_fails(fail, loader.device_fqdns))
        total = len(success) + len(fail)
        if not total:
            get_logger().error("No devices found for %s", args.query)
        output_driver.write_output(args, out, total)


@subcommand(cli_args.DeployOptions)
def deploy(args: cli_args.DeployOptions):
    """ Сгенерировать конфиг для устройств и задеплоить его """

    deployer = Deployer(args)
    filterer = filtering.filterer_connector.get()
    fetcher = fetcher_connector.get()
    deploy_driver = driver_connector.get()

    with get_loader(args, args) as loader:
        return api.deploy(
            args=args, loader=loader, deployer=deployer,
            deploy_driver=deploy_driver, filterer=filterer,
            fetcher=fetcher,
        )


@subcommand(cli_args.FileDiffOptions)
def file_diff(args: cli_args.FileDiffOptions):
    """ Показать дифф по рулбуку между файлами или каталогами """
    (success, fail) = api.file_diff(args)
    out = []
    output_driver = output_driver_connector.get()
    if not args.fails_only:
        out.extend(item for items in success.values() for item in items)
    out.extend(output_driver.format_fails(fail))
    # todo отрефакторить логику с отображением хоста в диффе: передавать в write_output явно критерий
    output_driver.write_output(args, out, len(out) + 1)


@subcommand(cli_args.FilePatchOptions)
def file_patch(args: cli_args.FilePatchOptions):
    """ Сформировать патч для файлов или каталогов """
    (success, fail) = api.file_patch(args)
    out = []
    output_driver = output_driver_connector.get()
    if not args.fails_only:
        out.extend(item for items in success.values() for item in items)
    out.extend(output_driver.format_fails(fail))
    output_driver.write_output(args, out, len(out))


@subcommand()
def context():
    """ Операции для управления файлом контекста.

    По-умолчанию находится в '~/.annushka/context.yml', либо по пути в переменной окружения ANN_CONTEXT_CONFIG_PATH.
    """
    context_touch()


@subcommand(parent=context)
def context_touch():
    """ Вывести путь к файлу контекста и, при отсутствии, создать его и наполнить данными (команда по-умолчанию) """
    print(get_context_path(touch=True))


@subcommand(cli_args.SelectContext, parent=context)
def context_set_context(args: cli_args.SelectContext):
    """ Задать текущий активный контекст по имени в конфигурации

    Выбранный контекст будет использоваться по-умолчанию при незаданной переменной окружения ANN_SELECTED_CONTEXT
    """
    with open(path := get_context_path(touch=True)) as f:
        data = yaml.safe_load(f)
    if args.context_name not in data.get("context", {}):
        raise KeyError(f"Cannot select context with name '{args.context_name}'. "
                       f"Available options are: {list(data.get('context', []))}")
    data["selected_context"] = args.context_name
    with open(path, "w") as f:
        yaml.dump(data, f, sort_keys=False)


@subcommand(parent=context)
def context_edit():
    """ Открыть файл конфигурации контекста в редакторе из переменной окружения EDITOR

    Если переменная окружения EDITOR не задана,
    для Windows пытаемся открыть файл средствами ОС, для остальных случаев пытаемся открыть в vi
    """
    editor = ""
    if e := os.getenv("EDITOR"):
        editor = e
    elif platform.system() == "Windows":
        editor = "notepad.exe"
    elif shutil.which("vim"):
        editor = "vim"
    else:
        editor = "vi"
    path = get_context_path(touch=True)
    proc = subprocess.Popen([editor, path])
    proc.wait()


@subcommand(parent=context)
def context_repair():
    """ Попытаться исправить расхождения в формате файла контекста после изменении версии """
    repair_context_file()
