from __future__ import annotations

import dataclasses
import itertools
import json
import os
import sys
import textwrap
import time
from collections import OrderedDict as odict
from operator import itemgetter
from typing import (
    Any,
    Dict,
    FrozenSet,
    Generator,
    Iterable,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
)

import tabulate
from contextlog import get_logger

from annet import generators, implicit, patching, tabparser, tracing
from annet.annlib import jsontools
from annet.annlib.rbparser import platform
from annet.annlib.rbparser.acl import compile_acl_text
from annet.cli_args import DeployOptions, GenOptions, ShowGenOptions
from annet.deploy import fetcher_connector, scrub_config
from annet.filtering import Filterer
from annet.generators import (
    BaseGenerator,
    Entire,
    GeneratorError,
    JSONFragment,
    NotSupportedDevice,
    PartialGenerator,
    RefGenerator,
)
from annet.lib import merge_dicts, percentile
from annet.output import output_driver_connector
from annet.parallel import Parallel
from annet.storage import Device, Storage, storage_connector
from annet.tracing import tracing_connector
from annet.types import OldNewResult


# Вывод всех генераторов вместе.
# Значение такое же, как для аналогичной константы в ЧК.
ALL_GENS = "_all_gens"

live_configs = None


@dataclasses.dataclass
class DeviceGenerators:
    """Collections of various types of generators found for devices."""

    # map device fqdn to found partial generators
    partial: Dict[Any, List[PartialGenerator]] = dataclasses.field(default_factory=dict)

    # ref generators
    ref: Dict[Any, List[RefGenerator]] = dataclasses.field(default_factory=dict)

    # map device fqdn to found entire generators
    entire: Dict[Any, List[Entire]] = dataclasses.field(default_factory=dict)

    # map device fqdn to found json fragment generators
    json_fragment: Dict[Any, List[JSONFragment]] = dataclasses.field(default_factory=dict)

    def iter_gens(self) -> Iterator[BaseGenerator]:
        """Iterate over generators."""
        for device_to_gens_of_the_same_type in (self.partial, self.entire, self.json_fragment):
            for gen_list in device_to_gens_of_the_same_type.values():
                for gen in gen_list:
                    yield gen

    def file_gens(self, device: Any) -> Iterator[Union[Entire, JSONFragment]]:
        """Iterate over generators that generate files or file parts."""
        yield from itertools.chain(
            self.entire.get(device, []),
            self.json_fragment.get(device, []),
        )

    def update(self, other: "DeviceGenerators") -> None:
        self.partial.update(other.partial)
        self.ref.update(other.ref)
        self.entire.update(other.entire)
        self.json_fragment.update(other.json_fragment)


@dataclasses.dataclass
class OldNewDeviceContext:
    config: str
    args: GenOptions
    downloaded_files: Dict[Device, DeviceDownloadedFiles]
    failed_files: Dict[Device, Exception]
    running: Dict[Device, Dict[str, str]]
    failed_running: Dict[Device, Exception]
    no_new: bool
    stdin: Optional[Dict[str, Optional[str]]]
    add_annotations: bool
    add_implicit: bool
    do_files_download: bool
    gens: DeviceGenerators
    fetched_packages: Dict[Device, FrozenSet[str]]
    failed_packages: Dict[Device, Exception]
    device_count: int
    do_print_perf: bool


@tracing.function
def _old_new_per_device(ctx: OldNewDeviceContext, device: Device, filterer: Filterer) -> OldNewResult:
    tracing_connector.get().set_device_attributes(tracing_connector.get().get_current_span(), device)

    start = time.monotonic()
    acl_rules = None
    acl_safe_rules = None
    old = odict()
    safe_old = odict()
    old_files = DeviceDownloadedFiles()
    new = odict()
    safe_new = odict()
    combined_perf = {}
    partial_results = []
    entire_results = []
    implicit_rules: Optional[Dict[str, Any]] = None
    filter_acl_rules: Optional[Dict[str, Any]] = None
    old_json_fragment_files: Dict[str, Dict[str, Any]] = {}
    new_json_fragment_files: Dict[str, Dict[str, Any]] = {}
    json_fragment_results: Dict[str, generators.GeneratorJSONFragmentResult] = {}

    if not device.is_pc():
        try:
            text = _old_new_get_config_cli(ctx, device)
        except Exception as exc:
            return OldNewResult(device=device, err=exc)

        if not text and ctx.args.fail_on_empty_config:
            return OldNewResult(
                device=device,
                err=Exception("no existing config retrieved (method: %s)" % ctx.config),
            )

        old = odict()
        if ctx.config != "empty":
            old = tabparser.parse_to_tree(
                text=text,
                splitter=tabparser.make_formatter(device.hw).split,
            )
        if not old:
            res = generators.run_partial_initial(device)
            old = res.config_tree()
            perf = res.perf_mesures()
            if ctx.args.profile and ctx.do_print_perf:
                _print_perf("INITIAL", perf)
        run_args = generators.GeneratorPartialRunArgs(
            device=device,
            use_acl=not ctx.args.no_acl,
            use_acl_safe=ctx.args.acl_safe,
            annotate=ctx.add_annotations,
            generators_context=ctx.args.generators_context,
            no_new=ctx.no_new,
        )
        res = generators.run_partial_generators(
            ctx.gens.partial[device],
            ctx.gens.ref[device],
            run_args,
        )
        partial_results = res.partial_results
        perf = res.perf_mesures()
        if ctx.no_new:
            new = odict()
            safe_new = odict()
        elif partial_results:
            # skip one gen with not supported device
            new = res.config_tree()
            safe_new = res.config_tree(safe=True)

        if ctx.args.profile:
            if ctx.do_print_perf:
                _print_perf("PARTIAL", perf)
            combined_perf.update(perf)

        implicit_rules = implicit.compile_rules(device)
        if ctx.add_implicit:
            old = merge_dicts(old, implicit.config(old, implicit_rules))
            new = merge_dicts(new, implicit.config(new, implicit_rules))
            safe_new = merge_dicts(safe_new, implicit.config(safe_new, implicit_rules))

        if not ctx.args.no_acl:
            acl_rules = generators.compile_acl_text(res.acl_text(), device.hw.vendor)
            old = (old and patching.apply_acl(old, acl_rules))

            new = patching.apply_acl(
                new,
                acl_rules,
                exclusive=not ctx.args.no_acl_exclusive,
                with_annotations=ctx.add_annotations,
            )
            if ctx.args.acl_safe:
                acl_safe_rules = generators.compile_acl_text(res.acl_safe_text(), device.hw.vendor)
                safe_old = (old and patching.apply_acl(old, acl_safe_rules))
                safe_new = patching.apply_acl(
                    safe_new,
                    acl_safe_rules,
                    exclusive=not ctx.args.no_acl_exclusive,
                    with_annotations=ctx.add_annotations,
                )

        filter_acl_rules = build_filter_acl(filterer, device, ctx.stdin, ctx.args, ctx.config)
        if filter_acl_rules is not None:
            old = (old and patching.apply_acl(old, filter_acl_rules, fatal_acl=False))
            new = patching.apply_acl(
                new,
                filter_acl_rules,
                fatal_acl=False,
                with_annotations=ctx.add_annotations,
            )
    else:  # vendor == pc
        try:
            old_files = _old_new_get_config_files(ctx, device)
        except Exception as exc:
            return OldNewResult(device=device, err=exc)

    new_files = {}
    safe_new_files = {}
    safe_new_json_fragment_files = {}
    if not ctx.no_new:
        if device in ctx.fetched_packages:
            if ctx.args.required_packages_check:
                errors = generators.check_entire_generators_required_packages(ctx.gens.entire[device.fqdn],
                                                                              ctx.fetched_packages[device])
                if errors:
                    error_msg = "; ".join(errors)
                    get_logger(host=device.hostname).error(error_msg)
                    return OldNewResult(device=device, err=Exception(error_msg))
        res = generators.run_file_generators(
            ctx.gens.file_gens(device),
            device,
        )

        entire_results = res.entire_results
        json_fragment_results = res.json_fragment_results
        old_json_fragment_files = old_files.json_fragment_files

        new_files = res.new_files()
        new_json_fragment_files = res.new_json_fragment_files(old_json_fragment_files)

        filters: List[str] = []
        filters_text = build_filter_text(filterer, device, ctx.stdin, ctx.args, ctx.config)
        if filters_text:
            filters = filters_text.split("\n")

            for file_name in new_json_fragment_files:
                if new_json_fragment_files.get(file_name) is not None:
                    new_json_fragment_files = _update_json_config(
                        new_json_fragment_files,
                        file_name,
                        jsontools.apply_acl_filters(new_json_fragment_files[file_name][0], filters)
                    )
            for file_name in old_json_fragment_files:
                if old_json_fragment_files.get(file_name) is not None:
                    old_json_fragment_files[file_name] = jsontools.apply_acl_filters(old_json_fragment_files[file_name], filters)

        if ctx.args.acl_safe:
            safe_new_files = res.new_files(safe=True)
            safe_new_json_fragment_files = res.new_json_fragment_files(old_json_fragment_files, safe=True)
            if filters:
                for file_name in safe_new_json_fragment_files:
                    if safe_new_json_fragment_files.get(file_name):
                        safe_new_json_fragment_files = _update_json_config(
                            safe_new_json_fragment_files,
                            file_name,
                            jsontools.apply_acl_filters(safe_new_json_fragment_files[file_name][0], filters)
                        )

    if ctx.args.profile:
        perf = res.perf_mesures()
        combined_perf[ALL_GENS] = {"total": time.monotonic() - start}
        combined_perf.update(perf)
        if ctx.do_print_perf:
            _print_perf("ENTIRE", perf)

    return OldNewResult(
        device=device,
        old=old,
        new=new,
        acl_rules=acl_rules,
        old_files=old_files.entire_files,
        new_files=new_files,
        partial_result=partial_results,
        entire_result=entire_results,
        old_json_fragment_files=old_json_fragment_files,
        new_json_fragment_files=new_json_fragment_files,
        json_fragment_result=json_fragment_results,
        implicit_rules=implicit_rules,
        perf=combined_perf,
        acl_safe_rules=acl_safe_rules,
        safe_old=safe_old,
        safe_new=safe_new,
        safe_new_files=safe_new_files,
        safe_new_json_fragment_files=safe_new_json_fragment_files,
        filter_acl_rules=filter_acl_rules,
    )


def _update_json_config(json_files, file_name, new_config):
    file = list(json_files[file_name])
    file[0] = new_config
    json_files[file_name] = tuple(file)
    return json_files


@dataclasses.dataclass
class DeviceDownloadedFiles:
    # map file path to file content for entire generators
    entire_files: Dict[str, str] = dataclasses.field(default_factory=dict)

    # map file path to file content for json fragment generators
    json_fragment_files: Dict[str, Dict[str, Any]] = dataclasses.field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.entire_files and not self.json_fragment_files


def split_downloaded_files(
        device_flat_files: Dict[str, Optional[str]],
        gens: DeviceGenerators,
        device: Device,
) -> DeviceDownloadedFiles:
    """Split downloaded files per generator type: entire/json_fragment."""
    ret = DeviceDownloadedFiles()

    for gen in gens.file_gens(device):
        filepath = gen.path(device)
        if filepath in device_flat_files:
            if isinstance(gen, Entire):
                ret.entire_files[filepath] = device_flat_files[filepath]
            elif isinstance(gen, JSONFragment):
                if device_flat_files[filepath] is not None:  # file exists
                    ret.json_fragment_files[filepath] = json.loads(device_flat_files[filepath])
                else:
                    ret.json_fragment_files[filepath] = None

    return ret


def split_downloaded_files_multi_device(
        flat_downloaded_files: Dict[Device, Dict[str, Optional[str]]],
        gens: DeviceGenerators,
        devices: List[Device],
) -> Dict[str, DeviceDownloadedFiles]:
    """Split downloaded files per generator type: entire/json_fragment."""
    return {
        device: split_downloaded_files(flat_downloaded_files[device], gens, device)
        for device in devices
        if device in flat_downloaded_files
    }


# ====
@tracing.function
def old_new(
    args: GenOptions,
    config: str,
    loader: "Loader",
    filterer: Filterer,
    add_implicit=True,
    add_annotations=False,
    stdin=None,
    device_ids: List[int] = None,
    no_new=False,
    do_files_download=False,
    do_print_perf=True,
):
    devices = loader.devices
    gens = loader.resolve_gens(devices)
    running, failed_running = _old_resolve_running(config, devices)
    downloaded_files, failed_files = _old_resolve_files(config, devices, gens, do_files_download)

    if stdin is None:
        stdin = args.stdin(filter_acl=args.filter_acl, config=config)

    fetched_packages, failed_packages = {}, {}
    if do_files_download and config == "running":
        files_to_download = _get_files_to_download(devices, gens)
        devices_with_files = [device for device in devices if device in files_to_download]
        fetcher = fetcher_connector.get()
        fetched_packages, failed_packages = fetcher.fetch_packages(devices_with_files)

    ctx = OldNewDeviceContext(
        config=config,
        args=args,
        downloaded_files=split_downloaded_files_multi_device(downloaded_files, gens, devices),
        failed_files=failed_files,
        running=running,
        failed_running=failed_running,
        no_new=no_new,
        stdin=stdin,
        add_annotations=add_annotations,
        add_implicit=add_implicit,
        do_files_download=do_files_download,
        gens=gens,
        fetched_packages=fetched_packages,
        failed_packages=failed_packages,
        device_count=len(devices),
        do_print_perf=do_print_perf,
    )
    for device in devices:
        logger = get_logger(host=device.hostname)
        try:
            result = _old_new_per_device(ctx, device, filterer)
        except patching.AclNotExclusiveError as err:
            logger.error("ACL error: more than one acl rules matches to this command: %s", err)
            raise GeneratorError from err
        if result is not None:
            yield result


@tracing.function
def old_raw(
        args: GenOptions, loader: Loader, config, stdin=None,
        do_files_download=False, use_mesh=True,
) -> Iterable[Tuple[Device, Union[str, Dict[str, str]]]]:
    device_gens = loader.resolve_gens(loader.devices)
    running, failed_running = _old_resolve_running(config, loader.devices)
    downloaded_files, failed_files = _old_resolve_files(config, loader.devices, device_gens, do_files_download)
    if stdin is None:
        stdin = args.stdin(filter_acl=args.filter_acl, config=config)
    ctx = OldNewDeviceContext(
        config=config,
        args=args,
        downloaded_files=split_downloaded_files_multi_device(downloaded_files, device_gens, loader.devices),
        failed_files=failed_files,
        running=running,
        failed_running=failed_running,
        stdin=stdin,
        do_files_download=do_files_download,
        device_count=len(loader.devices),
        no_new=True,
        add_annotations=False,
        add_implicit=False,
        gens=DeviceGenerators(),
        fetched_packages={},
        failed_packages={},
        do_print_perf=True,
    )
    for device in loader.devices:
        if not device.is_pc():
            config = _old_new_get_config_cli(ctx, device)
            config = scrub_config(config, device.breed)
            yield device, config
        else:
            files = _old_new_get_config_files(ctx, device)
            if files.entire_files:
                yield device, files.entire_files
            if files.json_fragment_files:
                yield device, {
                    path: jsontools.format_json(data)
                    for path, data in files.json_fragment_files.items()
                }


@tracing.function
def worker(device_id, args: ShowGenOptions, stdin, loader: "Loader", filterer: Filterer) -> Generator[Tuple[str, str, bool], None, None]:
    span = tracing_connector.get().get_current_span()
    if span:
        span.set_attribute("device.id", device_id)

    for res in old_new(
        args,
        config="/dev/null",
        loader=loader,
        filterer=filterer,
        add_implicit=False,
        add_annotations=args.annotate,
        stdin=stdin,
        device_ids=[device_id],
    ):
        new = res.get_new(args.acl_safe)
        new_files = res.get_new_files(args.acl_safe)
        new_file_fragments = res.get_new_file_fragments(args.acl_safe)
        output_driver = output_driver_connector.get()
        device = res.device
        if new is None:
            continue
        for (entire_path, (entire_data, _)) in sorted(new_files.items(), key=itemgetter(0)):
            yield (output_driver.entire_config_dest_path(device, entire_path), entire_data, False)

        for (path, (data, _)) in sorted(new_file_fragments.items(), key=itemgetter(0)):
            dumped_data = json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)
            yield (output_driver.entire_config_dest_path(device, path), dumped_data, False)

        has_file_result = new_files or new_file_fragments
        has_partial_result = new or not has_file_result
        if device.hw.vendor in platform.VENDOR_REVERSES and has_partial_result:
            orderer = patching.Orderer.from_hw(device.hw)
            yield (output_driver.cfg_file_names(device)[0],
                   format_config_blocks(
                       orderer.order_config(new),
                       device.hw,
                       args.indent
                   ),
                   False)


def old_new_worker(device_id, args: DeployOptions, config, stdin, loader: "Loader", filterer: Filterer):
    yield from old_new(
        args,
        config=config,
        loader=loader,
        filterer=filterer,
        stdin=stdin,
        device_ids=[device_id],
        no_new=args.clear,
        do_files_download=True,
    )


class OldNewParallel(Parallel):
    def __init__(self, args: DeployOptions, loader: "Loader", filterer: Filterer):
        stdin = args.stdin(filter_acl=args.filter_acl, config=args.config)
        super().__init__(
            old_new_worker,
            args,
            config=args.config,
            stdin=stdin,
            loader=loader,
            filterer=filterer,
        )
        self.tune_args(args)

    def generated_configs(self, devices: List[Device]) -> Generator[OldNewResult, None, None]:
        devices_by_id = {device.id: device for device in devices}
        device_ids = list(devices_by_id)

        for task_result in self.irun(device_ids):
            if task_result.exc is not None:
                device = devices_by_id.pop(task_result.device_id)
                yield OldNewResult(device=device, err=task_result.exc)
            elif task_result.result is not None:
                yield from task_result.result
                devices_by_id.pop(task_result.device_id)

        for device in devices_by_id.values():
            yield OldNewResult(device=device, err=Exception(f"No config returned for {device.hostname}"))


@dataclasses.dataclass
class DeviceFilesToDownload:
    entire: List[str] = dataclasses.field(default_factory=list)
    json_fragment: List[str] = dataclasses.field(default_factory=list)


@tracing.function
def _get_files_to_download(devices: List[Device], gens: DeviceGenerators) -> Dict[Device, Any]:
    files_to_download = {}
    for device in devices:
        paths = set()
        try:
            for generator in gens.file_gens(device):
                try:
                    path = generator.path(device)
                    if path:
                        paths.add(path)
                except NotSupportedDevice:
                    continue
        except Exception as exc:
            files_to_download[device] = exc
            continue
        if paths:
            files_to_download[device] = sorted(paths)
    return files_to_download


def _print_perf(gen_type, perf):
    print(file=sys.stderr)
    print(
        tabulate.tabulate([
                (
                    (gen if not method else None),
                    (method or "." * 30),
                    sum(map(itemgetter("time"), stat)),
                    (min(map(itemgetter("time"), stat)) if method else None),
                    (percentile(stat, 0.95, itemgetter("time")) if method else None),
                    (max(map(itemgetter("time"), stat)) if method else None),
                    (len(stat) if method else None),
                    (len(list(filter(
                                     lambda item: item in ["call", "disk_write"],
                                     map(itemgetter("op"), stat)))) if method else None),
                )

                for (gen, gen_perf) in sorted(
                    perf.items(),
                    key=(lambda item: item[1]["total"]),
                    reverse=True,
                )

                for (method, stat) in sorted(
                    [(None, [{"time": gen_perf["total"], "op": None}])] + list(gen_perf["rt"].items()),
                    key=(lambda item: sum(map(itemgetter("time"), item[1]))),
                    reverse=True,
                )
            ],
            [gen_type + "-Generator", "RT", "Total", "Min", "95%", "Max", "Calls", "Direct"],
            tablefmt="orgtbl", floatfmt=".4f",
        ),
        file=sys.stderr,
    )
    print(file=sys.stderr)


def build_filter_text(filterer, device, stdin, args, config):
    filter_acl_text = None
    if args.filter_acl:
        filter_acl_text = stdin["filter_acl"]
    if args.filter_acl and not stdin["filter_acl"]:
        if os.path.isdir(args.filter_acl):
            filename = os.path.join(config, "%s.acl" % device.hostname)
        else:
            filename = args.filter_acl
        with open(filename) as fh:
            filter_acl_text = fh.read()

    if args.filter_ifaces:
        filter_acl_text = filter_acl_text + "\n" if filter_acl_text else ""
        filter_acl_text += filterer.for_ifaces(device, args.filter_ifaces)

    if args.filter_peers:
        filter_acl_text = filter_acl_text + "\n" if filter_acl_text else ""
        filter_acl_text += filterer.for_peers(device, args.filter_peers)

    if args.filter_policies:
        filter_acl_text = filter_acl_text + "\n" if filter_acl_text else ""
        filter_acl_text += filterer.for_policies(device, args.filter_policies)
    return filter_acl_text


def build_filter_acl(filterer, device, stdin, args, config):
    filter_acl_text = build_filter_text(filterer, device, stdin, args, config)
    if filter_acl_text is not None:
        return compile_acl_text(
            textwrap.dedent(filter_acl_text),
            device.hw.vendor,
            allow_ignore=True,
        )


def _existing_cfg_file_name(config_dir: str, device) -> Optional[str]:
    cfg_files = output_driver_connector.get().cfg_file_names(device)
    last: Optional[str] = None
    for cfg_file in cfg_files:
        filename = os.path.join(config_dir, cfg_file)
        last = filename
        if os.path.exists(filename):
            return filename
    return last


def format_config_blocks(config, hw, indent, _level=0):
    formatter = tabparser.make_formatter(hw, indent=indent)
    return formatter.join(config)


def format_files(files):
    lines = []
    for path in sorted(files):
        lines.extend((
            "# %s" % path,
            files[path],
        ))
    return "\n".join(lines)


def find_files_relative(path: str) -> Generator[str, None, None]:
    """Рекурсивно найти файлы в path и вернуть пути к ним относительно path"""
    root_abs_path = os.path.abspath(path)
    for dirpath, _dirnames, filenames in os.walk(path):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            yield os.path.relpath(full_path, root_abs_path)


def load_pc_config(path: str, set_root=False) -> Dict[str, str]:
    """Подхватываем локально сохраненные файлы конфигов для вайтбоксов"""
    ret: Dict[str, str] = {}
    for relative_cfg_path in find_files_relative(path):
        with open(os.path.join(path, relative_cfg_path)) as cfg_file:
            text = cfg_file.read()
        if set_root:
            relative_cfg_path = os.path.join("/", relative_cfg_path)
        ret[relative_cfg_path] = text
    return ret


@tracing.function
def _old_new_get_config_cli(ctx: OldNewDeviceContext, device: Device) -> str:
    if ctx.config == "empty":
        text = ""
    elif ctx.config == "running":
        text = ctx.running.get(device)
        if text is None:
            exc = (ctx.failed_running.get(device.fqdn) or
                   ctx.failed_running.get(device.hostname) or
                   Exception("I can't get device config and I don't know why"))
            get_logger(host=device.hostname).error("config error %s", exc)
            raise exc
    elif ctx.config == "-":
        text = ctx.stdin["config"]
        if ctx.device_count > 1:
            raise ValueError("stdin config can not be used with multiple devices")
    else:
        if os.path.isdir(ctx.config):
            filename = _existing_cfg_file_name(ctx.config, device)
        else:
            filename = ctx.config
        try:
            with open(filename) as fh:
                text = fh.read()
        except Exception as exc_info:
            if not ctx.args.fail_on_empty_config and isinstance(exc_info, FileNotFoundError):
                return ""
            if ctx.device_count > 1:
                get_logger(host=device.hostname).error(str(exc_info))
                return None
            raise
    return text


@tracing.function
def _old_new_get_config_files(ctx: OldNewDeviceContext, device: Device) -> DeviceDownloadedFiles:
    old_files = DeviceDownloadedFiles()

    for attr in ("failed_files", "failed_running", "failed_packages"):
        if device in getattr(ctx, attr):
            exc = getattr(ctx, attr).get(device)
            exc = exc or Exception(f"I can't get device {attr[len('failed_'):]} and I don't know why")
            get_logger(host=device.hostname).error(str(exc))
            raise exc

    if ctx.do_files_download:
        if ctx.config == "empty":
            return old_files
        if ctx.config == "running":
            old_files_running = ctx.downloaded_files.get(device)
            if not old_files_running:
                return old_files
            old_files = old_files_running
        elif os.path.exists(ctx.config):
            # try to find config in subdirectory: <ctx.config>/<device_name>.cfg/
            config_path = _existing_cfg_file_name(ctx.config, device)
            if config_path is None:
                # if subdir does not exist, assume the whole dir is our config
                config_path = ctx.config
            if not os.path.isdir(config_path):
                get_logger(host=device.hostname).error("I can't find device files in %s", config_path)
                return old_files
            old_files = split_downloaded_files(load_pc_config(config_path, True), ctx.gens, device)
        else:
            raise NotImplementedError("pc and not running or path")
    return old_files


@tracing.function
def _old_resolve_gens(args: GenOptions, storage: Storage, devices: Iterable[Device]) -> DeviceGenerators:
    per_device_gens = DeviceGenerators()
    devices = devices or [None]  # get all generators if no devices provided
    for device in devices:
        gens = generators.build_generators(storage, gens=args, device=device)
        per_device_gens.partial[device] = gens.partial
        per_device_gens.entire[device] = gens.entire
        per_device_gens.json_fragment[device] = gens.json_fragment
        per_device_gens.ref[device] = gens.ref
    return per_device_gens


@tracing.function
def _old_resolve_running(config: str, devices: List[Device]) -> Tuple[Dict[Device, str], Dict[Device, Exception]]:
    running, failed_running = {}, {}
    if config == "running":
        global live_configs  # pylint: disable=global-statement
        if live_configs is None:
            # предварительно прочесть все конфиги прямо по ssh
            fetcher = fetcher_connector.get()
            running, failed_running = fetcher.fetch(devices)
        else:
            running, failed_running = live_configs  # pylint: disable=unpacking-non-sequence
    return running, failed_running


@tracing.function
def _old_resolve_files(config: str,
                       devices: List[Device],
                       gens: DeviceGenerators,
                       do_files_download: bool,
                       ) -> Tuple[Dict[Device, Dict[str, Optional[str]]], Dict[Device, Exception]]:
    downloaded_files, failed_files = {}, {}
    if do_files_download and config == "running":
        files_to_download = _get_files_to_download(devices, gens)
        devices_with_files = [device for device in devices if device in files_to_download]
        if devices_with_files:
            fetcher = fetcher_connector.get()
            downloaded_files, failed_files = fetcher.fetch(devices_with_files,
                                                           files_to_download=files_to_download)
    return downloaded_files, failed_files


class Loader:
    def __init__(
            self, *storages: Storage,
            args: GenOptions,
            no_empty_warning: bool = False,
    ) -> None:
        self._args = args
        self._storages = storages
        self._no_empty_warning = no_empty_warning
        self._devices_map: Dict[int, Device] = {}
        self._gens: DeviceGenerators = DeviceGenerators()
        self._counter = itertools.count()

        self._preload()

    def _preload(self) -> None:
        with tracing_connector.get().start_as_current_span("Resolve devices"):
            for storage in self._storages:
                devices = storage.make_devices(
                    self._args.query,
                    preload_neighbors=True,
                    use_mesh=not self._args.no_mesh,
                    preload_extra_fields=True,
                )
                for device in devices:
                    self._devices_map[next(self._counter)] = device
                self._gens.update(_old_resolve_gens(self._args, storage, devices))
        if not devices and not self._no_empty_warning:
            get_logger().error("No devices found for %s", self._args.query)
            return

    @property
    def device_fqdns(self):
        return {
            device_id: d.fqdn
            for device_id, d in self._devices_map.items()
        }

    @property
    def device_ids(self):
        return list(self._devices_map)

    @property
    def devices(self) -> List[Device]:
        if self._devices_map:
            return list(self._devices_map.values())
        return []

    def resolve_gens(self, devices: Iterable[Device]) -> DeviceGenerators:
        if self._gens is not None:
            return self._gens

        with tracing_connector.get().start_as_current_span("Resolve gens"):
            return _old_resolve_gens(self._args, self._storage, devices)
