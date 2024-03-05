import abc
import difflib
import os
import re
import sys
import time
from collections import OrderedDict as odict
from itertools import groupby
from operator import itemgetter
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

import colorama
from annet.annlib import jsontools
from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.rbparser.platform import VENDOR_REVERSES
from annet.annlib.types import GeneratorType
from contextlog import get_logger

import annet.deploy
from annet import cli_args
from annet import diff as ann_diff
from annet import filtering
from annet import gen as ann_gen
from annet import patching, rulebook, tabparser, tracing
from annet.hardware import hardware_connector
from annet.output import (
    LABEL_NEW_PREFIX,
    format_file_diff,
    output_driver_connector,
    print_err_label,
)
from annet.parallel import Parallel, TaskResult
from annet.reference import RefTracker
from annet.storage import Device, Storage, storage_connector
from annet.types import Diff, ExitCode, OldNewResult, Op, PCDiff, PCDiffFile


live_configs = ann_gen.live_configs

DEFAULT_INDENT = "  "


def patch_from_pre(pre, hw, rb, add_comments, ref_track=None, do_commit=True):
    if not ref_track:
        ref_track = RefTracker()
    orderer = patching.Orderer(rb["ordering"], hw.vendor)
    orderer.ref_insert(ref_track)
    return patching.make_patch(
        pre=pre,
        rb=rb,
        hw=hw,
        add_comments=add_comments,
        orderer=orderer,
        do_commit=do_commit,
    )


def _diff_and_patch(
    device, old, new, acl_rules, filter_acl_rules,
    add_comments, ref_track=None, do_commit=True, rb=None
) -> Tuple[Diff, Dict]:
    if rb is None:
        rb = rulebook.get_rulebook(device.hw)
    # [NOCDEV-5532] Передаем в diff только релевантные для logic'a части конфига
    if acl_rules is not None:
        old = patching.apply_acl(old, acl_rules)
        new = patching.apply_acl(new, acl_rules, with_annotations=add_comments)

    diff_tree = patching.make_diff(old, new, rb, [acl_rules, filter_acl_rules])
    pre = patching.make_pre(diff_tree)
    patch_tree = patch_from_pre(pre, device.hw, rb, add_comments, ref_track, do_commit)
    diff_tree = patching.strip_unchanged(diff_tree)

    return (diff_tree, patch_tree)


# =====
def _read_old_new_diff_patch(old: Dict[str, Dict], new: Dict[str, Dict], hw: HardwareView, add_comments: bool):
    rb = rulebook.get_rulebook(hw)
    diff_obj = patching.make_diff(old, new, rb, [])
    diff_obj = patching.strip_unchanged(diff_obj)
    pre = patching.make_pre(diff_obj)
    patchtree = patch_from_pre(pre, hw, rb, add_comments)
    return rb, diff_obj, pre, patchtree


def _read_old_new_hw(old_path: str, new_path: str, args: cli_args.FileInputOptions):
    _logger = get_logger()
    hw = args.hw
    if isinstance(args.hw, str):
        hw = HardwareView(args.hw, "")

    old, old_hw, old_score = _read_device_config(old_path, hw)
    new, new_hw, new_score = _read_device_config(new_path, hw)
    hw = new_hw
    if old_score > new_score:
        hw = old_hw
    if old_hw != new_hw:
        _logger.debug("Old and new detected hw differs, assume %r", hw)
    dest_name = os.path.basename(new_path)
    return dest_name, old, new, hw


@tracing.function
def _read_old_new_cfgdumps(args: cli_args.FileInputOptions):
    _logger = get_logger()
    old_path, new_path = os.path.normpath(args.old), os.path.normpath(args.new)
    if not os.path.isdir(old_path):
        yield (old_path, new_path)
        return
    _logger.info("Scanning cfgdumps: %s/*.cfg ...", old_path)
    cfgdump_reg = re.compile(r"^[^\s]+\.cfg$")
    if os.path.isdir(old_path) and os.path.isdir(new_path):
        if cfgdump_reg.match(os.path.basename(old_path)) and cfgdump_reg.match(os.path.basename(new_path)):
            yield (old_path, new_path)
    for name in os.listdir(old_path):
        old_path_name = os.path.join(old_path, name)
        new_path_name = os.path.join(new_path, name)
        if not os.path.exists(new_path_name):
            _logger.debug("Ignoring file %s: not exist %s", name, new_path_name)
            continue
        yield (old_path_name, new_path_name)


def _read_device_config(path, hw):
    _logger = get_logger()
    _logger.debug("Reading %r ...", path)
    score = 1

    with open(path) as cfgdump_file:
        text = cfgdump_file.read()
    try:
        if not hw:
            hw, score = guess_hw(text)
        config = tabparser.parse_to_tree(
            text=text,
            splitter=tabparser.make_formatter(hw).split,
        )
        return config, hw, score
    except tabparser.ParserError:
        _logger.exception("Parser error: %r", path)
        raise


# =====
def _format_patch_blocks(patch_tree, hw, indent):
    formatter = tabparser.make_formatter(hw, indent=indent)
    return formatter.patch(patch_tree)


# =====
def _print_pre_as_diff(pre, show_rules, indent, file=None, _level=0):
    for (raw_rule, content) in sorted(pre.items(), key=itemgetter(0)):
        rule_printed = False
        for (op, sign) in [  # FIXME: Not very effective
            (Op.REMOVED, colorama.Fore.RED + "-"),
            (Op.ADDED, colorama.Fore.GREEN + "+"),
            (Op.AFFECTED, colorama.Fore.CYAN + " "),
        ]:
            items = content["items"].items()
            if not content["attrs"]["multiline"]:
                items = sorted(items, key=itemgetter(0))
            for (_, diff) in items:  # pylint: disable=redefined-outer-name
                if show_rules and not rule_printed and not raw_rule == "__MULTILINE_BODY__":
                    print("%s%s# %s%s%s" % (colorama.Style.BRIGHT, colorama.Fore.BLACK, (indent * _level),
                                            raw_rule, colorama.Style.RESET_ALL), file=file)
                    rule_printed = True
                for item in sorted(diff[op], key=itemgetter("row")):
                    print("%s%s%s %s%s" % (colorama.Style.BRIGHT, sign, (indent * _level),
                                           item["row"], colorama.Style.RESET_ALL), file=file)
                    if len(item["children"]) != 0:
                        _print_pre_as_diff(item["children"], show_rules, indent, file, _level + 1)
                        rule_printed = False


def log_host_progress_cb(pool: Parallel, task_result: TaskResult):
    progress_logger = get_logger("progress")
    args = cast(cli_args.QueryOptions, pool.args[0])
    with storage_connector.get().storage()(args) as storage:
        hosts = storage.resolve_fdnds_by_query(args.query)
    perc = int(pool.tasks_done / len(hosts) * 100)
    fqdn = hosts[task_result.device_id]
    elapsed_time = "%dsec" % int(time.monotonic() - task_result.extra["start_time"])
    if task_result.extra.get("regression", False):
        status = task_result.extra["status"]
        status_color = task_result.extra["status_color"]
        message = task_result.extra["message"]
    else:
        status = "OK" if task_result.exc is None else "FAIL"
        status_color = colorama.Fore.GREEN if status == "OK" else colorama.Fore.RED
        message = "" if status == "OK" else str(task_result.exc)
    progress_logger.info(message,
                         perc=perc, fqdn=fqdn, status=status, status_color=status_color,
                         worker=task_result.worker_name, task_time=elapsed_time)
    return task_result


# =====
def gen(args: cli_args.ShowGenOptions):
    """ Сгенерировать конфиг для устройств """
    with storage_connector.get().storage()(args) as storage:
        loader = ann_gen.Loader(storage, args)
        stdin = args.stdin(storage=storage, filter_acl=args.filter_acl, config=None)

    filterer = filtering.filterer_connector.get()
    pool = Parallel(ann_gen.worker, args, stdin, loader, filterer).tune_args(args)
    if args.show_hosts_progress:
        pool.add_callback(log_host_progress_cb)

    return pool.run(loader.device_ids, args.tolerate_fails, args.strict_exit_code)


# =====
def _diff_file(old_text: Optional[str], new_text: Optional[str], context=3):
    old_lines = old_text.splitlines() if old_text else []
    new_lines = new_text.splitlines() if new_text else []
    context = max(len(old_lines), len(new_lines)) if context is None else context
    return list(difflib.unified_diff(old_lines, new_lines, n=context, lineterm=""))


def _diff_files(old_files, new_files, context=3):
    ret = {}
    for (path, (new_text, reload_data)) in new_files.items():
        old_text = old_files.get(path)
        is_new = old_text is None
        diff_lines = _diff_file(old_text, new_text, context=context)
        ret[path] = (diff_lines, reload_data, is_new)
    return ret


def patch(args: cli_args.ShowPatchOptions):
    """ Сгенерировать патч для устройств """
    global live_configs  # pylint: disable=global-statement
    with storage_connector.get().storage()(args) as storage:
        loader = ann_gen.Loader(storage, args)
        if args.config == "running":
            fetcher = annet.deploy.fetcher_connector.get()
            live_configs = fetcher.fetch(loader.devices, processes=args.parallel)
        stdin = args.stdin(storage=storage, filter_acl=args.filter_acl, config=args.config)

    filterer = filtering.filterer_connector.get()
    pool = Parallel(_patch_worker, args, stdin, loader, filterer).tune_args(args)
    if args.show_hosts_progress:
        pool.add_callback(log_host_progress_cb)
    return pool.run(loader.device_ids, args.tolerate_fails, args.strict_exit_code)


def _patch_worker(device_id, args: cli_args.ShowPatchOptions, stdin, loader: ann_gen.Loader, filterer: filtering.Filterer):
    for res, _, patch_tree in res_diff_patch(device_id, args, stdin, loader, filterer):
        new_files = res.get_new_files(args.acl_safe)
        new_json_fragment_files = res.get_new_file_fragments(args.acl_safe)
        if new_files:
            for path, (cfg_text, _cmds) in new_files.items():
                label = res.device.hostname + os.sep + path
                yield label, cfg_text, False
        elif res.old_json_fragment_files or new_json_fragment_files:
            for path, (new_json_cfg, _cmds) in new_json_fragment_files.items():
                label = res.device.hostname + os.sep + path
                old_json_cfg = res.old_json_fragment_files[path]
                json_patch = jsontools.make_patch(old_json_cfg, new_json_cfg)
                yield (
                    label,
                    jsontools.format_json(json_patch),
                    False,
                )
        elif patch_tree:
            yield (
                "%s.patch" % res.device.hostname,
                _format_patch_blocks(patch_tree, res.device.hw, args.indent),
                False,
            )


# =====
def res_diff_patch(device_id, args: cli_args.ShowPatchOptions, stdin, loader: ann_gen.Loader, filterer: filtering.Filterer) -> Iterable[
    Tuple[OldNewResult, Dict, Dict]]:
    with storage_connector.get().storage()(args) as storage:
        for res in ann_gen.old_new(
            args,
            storage,
            config=args.config,
            loader=loader,
            filterer=filterer,
            stdin=stdin,
            device_ids=[device_id],
            no_new=args.clear,
            do_files_download=True,
        ):
            old = res.get_old(args.acl_safe)
            new = res.get_new(args.acl_safe)
            new_json_fragment_files = res.get_new_file_fragments(args.acl_safe)

            device = res.device
            acl_rules = res.get_acl_rules(args.acl_safe)
            if res.old_json_fragment_files or new_json_fragment_files:
                yield res, None, None
            elif old is not None:
                (diff_tree, patch_tree) = _diff_and_patch(device, old, new, acl_rules, res.filter_acl_rules,
                                                          args.add_comments)
                yield res, diff_tree, patch_tree


def diff(args: cli_args.DiffOptions, loader: ann_gen.Loader, filterer: filtering.Filterer) -> Mapping[Device, Union[Diff, PCDiff]]:
    ret = {}
    with storage_connector.get().storage()(args) as storage:
        for res in ann_gen.old_new(
            args,
            storage,
            config=args.config,
            loader=loader,
            no_new=args.clear,
            do_files_download=True,
            device_ids=loader.device_ids,
            filterer=filterer,
        ):
            old = res.get_old(args.acl_safe)
            new = res.get_new(args.acl_safe)
            device = res.device
            acl_rules = res.get_acl_rules(args.acl_safe)
            new_files = res.get_new_files(args.acl_safe)
            new_json_fragment_files = res.get_new_file_fragments()
            pc_diff_files = []
            if res.old_files or new_files:
                pc_diff_files.extend(_pc_diff(device.hostname, res.old_files, new_files))
            if res.old_json_fragment_files or new_json_fragment_files:
                pc_diff_files.extend(_json_fragment_diff(device.hostname, res.old_json_fragment_files, new_json_fragment_files))

            if pc_diff_files:
                pc_diff_files.sort(key=lambda f: f.label)
                ret[device] = PCDiff(hostname=device.hostname, diff_files=pc_diff_files)
            elif old is not None:
                rb = rulebook.get_rulebook(device.hw)
                diff_tree = patching.make_diff(old, new, rb, [acl_rules, res.filter_acl_rules])
                diff_tree = patching.strip_unchanged(diff_tree)
                ret[device] = diff_tree
    return ret


def collapse_texts(texts: Mapping[str, str]) -> Mapping[Tuple[str, ...], str]:
    """
    Группировка текстов.
    :param texts:
    :return: словарь с несколькими хостнеймами в ключе.
    """
    diffs_with_orig = {key: [value, value.splitlines()] for key, value in texts.items()}
    res = {}
    for _, collapsed_diff_iter in groupby(sorted(diffs_with_orig.items(), key=lambda x: (x[0], x[1][1])),
                                          key=lambda x: x[1][1]):
        collapsed_diff = list(collapsed_diff_iter)
        res[tuple(x[0] for x in collapsed_diff)] = collapsed_diff[0][1][0]

    return res


class DeployerJob(abc.ABC):
    def __init__(self, device, args: cli_args.DeployOptions):
        self.args = args
        self.device = device
        self.add_comments = False
        self.diff_lines = []
        self.cmd_lines: List[str] = []
        self.deploy_cmds = odict()
        self.diffs = {}
        self.failed_configs = {}
        self._has_diff = False

    @abc.abstractmethod
    def parse_result(self, res):
        pass

    def collapseable_diffs(self):
        return {}

    def has_diff(self):
        return self._has_diff

    @staticmethod
    def from_device(device, args: cli_args.DeployOptions):
        if device.hw.vendor == "pc":
            return PCDeployerJob(device, args)
        return CliDeployerJob(device, args)


class CliDeployerJob(DeployerJob):
    def parse_result(self, res: OldNewResult):
        device = res.device
        old = res.get_old(self.args.acl_safe)
        new = res.get_new(self.args.acl_safe)
        acl_rules = res.get_acl_rules(self.args.acl_safe)
        err = res.err

        if err:
            self.failed_configs[device.fqdn] = err
            return

        (diff_obj, patch_tree) = _diff_and_patch(device, old, new, acl_rules,
                                                 res.filter_acl_rules, self.add_comments,
                                                 do_commit=not self.args.dont_commit)
        cmds = tabparser.make_formatter(device.hw, indent="").cmd_paths(patch_tree)
        if not cmds:
            return
        self._has_diff = True
        self.diffs[device] = diff_obj
        self.cmd_lines.extend(["= %s " % device.hostname, ""])
        self.cmd_lines.extend(map(itemgetter(-1), cmds))
        self.cmd_lines.append("")
        deployer_driver = annet.deploy.driver_connector.get()
        self.deploy_cmds[device] = deployer_driver.apply_deploy_rulebook(
            device.hw, cmds,
            do_commit=not self.args.dont_commit
        )
        for cmd in deployer_driver.build_exit_cmdlist(device.hw):
            self.deploy_cmds[device].add_cmd(cmd)

    def collapseable_diffs(self):
        return self.diffs


class PCDeployerJob(DeployerJob):
    def parse_result(self, res: ann_gen.OldNewResult):
        device = res.device
        old_files = res.old_files
        new_files = res.get_new_files(self.args.acl_safe)
        old_json_fragment_files = res.old_json_fragment_files
        new_json_fragment_files = res.get_new_file_fragments(self.args.acl_safe)
        err = res.err

        if err:
            self.failed_configs[device.fqdn] = err
            return
        elif not new_files and not new_json_fragment_files:
            return

        upload_files: Dict[str, bytes] = {}
        reload_cmds: Dict[str, bytes] = {}
        generator_types: Dict[str, GeneratorType] = {}
        for generator_type, pc_files in [(GeneratorType.ENTIRE, new_files), (GeneratorType.JSON_FRAGMENT, new_json_fragment_files)]:
            for file, (file_content_or_json_cfg, cmds) in pc_files.items():
                if generator_type == GeneratorType.ENTIRE:
                    file_content: str = file_content_or_json_cfg
                    diff_content = "\n".join(_diff_file(old_files.get(file), file_content))
                else:  # generator_type == GeneratorType.JSON_FRAGMENT
                    old_json_cfg = old_json_fragment_files[file]
                    json_patch = jsontools.make_patch(old_json_cfg, file_content_or_json_cfg)
                    file_content = jsontools.format_json(json_patch)
                    old_text = jsontools.format_json(old_json_cfg)
                    new_text = jsontools.format_json(file_content_or_json_cfg)
                    diff_content = "\n".join(_diff_file(old_text, new_text))
                if diff_content:
                    self._has_diff = True
                upload_files[file], reload_cmds[file] = file_content.encode(), cmds.encode()
                generator_types[file] = generator_type
                self.cmd_lines.append("= Deploy cmds %s/%s " % (device.hostname, file))
                self.cmd_lines.extend([cmds, ""])
                self.cmd_lines.append("= %s/%s " % (device.hostname, file))
                self.cmd_lines.extend([file_content, ""])
                self.diff_lines.append("= %s/%s " % (device.hostname, file))
                self.diff_lines.extend([diff_content, ""])

        if upload_files:
            self.deploy_cmds[device] = {
                "files": upload_files,
                "cmds": reload_cmds,
                "generator_types": generator_types,
            }
            self.diffs[device] = upload_files
            deployer_driver = annet.deploy.driver_connector.get()
            before, after = deployer_driver.build_configuration_cmdlist(device.hw)
            for cmd in deployer_driver.build_exit_cmdlist(device.hw):
                after.add_cmd(cmd)
            cmds_pre_files = {}
            for file in self.deploy_cmds[device]["files"]:
                if before:
                    cmds_pre_files[file] = "\n".join(map(str, before)).encode(encoding="utf-8")
                self.deploy_cmds[device]["cmds"][file] += "\n".join(map(str, after)).encode(encoding="utf-8")
            self.deploy_cmds[device]["cmds_pre_files"] = cmds_pre_files


class Deployer:
    def __init__(self, args: cli_args.DeployOptions):
        self.args = args

        self.cmd_lines = []
        self.deploy_cmds = odict()
        self.diffs = {}
        self.failed_configs: Dict[str, Exception] = {}
        self.fqdn_to_device: Dict[str, Device] = {}
        self.empty_diff_hostnames: Set[str] = set()

        self._collapseable_diffs = {}
        self._diff_lines: List[str] = []
        self._filterer = filtering.filterer_connector.get()

    def parse_result(self, job: DeployerJob, result: ann_gen.OldNewResult):
        entire_reload = self.args.entire_reload
        logger = get_logger(job.device.hostname)

        job.parse_result(result)
        self.failed_configs.update(job.failed_configs)

        if job.has_diff() or entire_reload is entire_reload.force:
            self.cmd_lines.extend(job.cmd_lines)
            self.deploy_cmds.update(job.deploy_cmds)
            self.diffs.update(job.diffs)

            self.fqdn_to_device[result.device.fqdn] = result.device
            self._collapseable_diffs.update(job.collapseable_diffs())
            self._diff_lines.extend(job.diff_lines)
        else:
            logger.info("empty diff")

    def diff_lines(self) -> List[str]:
        diff_lines = []
        diff_lines.extend(self._diff_lines)
        for devices, diff_obj in ann_diff.collapse_diffs(self._collapseable_diffs).items():
            if not diff_obj:
                self.empty_diff_hostnames.update(dev.hostname for dev in devices)
            if not self.args.no_ask_deploy:
                # разобъем список устройств на несколько линий
                dest_name = ""
                try:
                    _, term_columns_str = os.popen("stty size", "r").read().split()
                    term_columns = int(term_columns_str)
                except Exception:
                    term_columns = 2 ** 32
                fqdns = [dev.hostname for dev in devices]
                while fqdns:
                    fqdn = fqdns.pop()
                    if len(dest_name) == 0:
                        dest_name = "= %s" % fqdn
                    elif len(dest_name) + len(fqdn) < term_columns:
                        dest_name = "%s, %s" % (dest_name, fqdn)
                    else:
                        diff_lines.extend([dest_name])
                        dest_name = "= %s" % fqdn
                    if not fqdns:
                        diff_lines.extend([dest_name, ""])
            else:
                dest_name = "= %s" % ", ".join([dev.hostname for dev in devices])
                diff_lines.extend([dest_name, ""])

            for line in tabparser.make_formatter(devices[0].hw).diff(diff_obj):
                diff_lines.append(line)
            diff_lines.append("")
        return diff_lines

    def ask_deploy(self) -> str:
        return self._ask("y", annet.deploy.AskConfirm(
            text="\n".join(self.diff_lines()),
            alternative_text="\n".join(self.cmd_lines),
        ))

    def ask_rollback(self) -> str:
        return self._ask("n", annet.deploy.AskConfirm(
            text="Execute rollback?\n",
            alternative_text="",
        ))

    def _ask(self, default_ans: str, ask: annet.deploy.AskConfirm) -> str:
        # если filter_acl из stdin то с ним уже не получится работать как с терминалом
        ans = default_ans
        if not self.args.no_ask_deploy:
            try:
                if not os.isatty(sys.stdin.fileno()):
                    pts_path = os.ttyname(sys.stdout.fileno())
                    pts = open(pts_path, "r")  # pylint: disable=consider-using-with
                    os.dup2(pts.fileno(), sys.stdin.fileno())
            except OSError:
                pass
            ans = ask.loop()
        return ans

    def check_diff(self, result: annet.deploy.DeployResult, storage: Storage):
        global live_configs  # pylint: disable=global-statement
        success_hosts = [
            host.split(".", 1)[0] for (host, hres) in result.results.items()
            if (not isinstance(hres, Exception) and
                host not in self.empty_diff_hostnames and
                not self.fqdn_to_device[host].is_pc())
        ]
        diff_args = self.args.copy_from(
            self.args,
            config="running",
            query=success_hosts,
        )
        if diff_args.query:
            live_configs = None
            loader = ann_gen.Loader(storage, diff_args, no_empty_warning=True)

            diffs = diff(diff_args, loader, self._filterer)
            non_pc_diffs = {dev: diff for dev, diff in diffs.items() if not isinstance(diff, PCDiff)}
            devices_to_diff = ann_diff.collapse_diffs(non_pc_diffs)
            devices_to_diff.update({(dev,): diff for dev, diff in diffs.items() if isinstance(diff, PCDiff)})
        else:
            devices_to_diff = {}
        for devices, diff_obj in devices_to_diff.items():
            if diff_obj:
                for dev in devices:
                    self.failed_configs[dev.fqdn] = Warning("Deploy OK, but diff still exists")
                if isinstance(diff_obj, PCDiff):
                    for diff_file in diff_obj.diff_files:
                        print_err_label(diff_file.label)
                        print("\n".join(format_file_diff(diff_file.diff_lines)))
                else:
                    output_driver = output_driver_connector.get()
                    dest_name = ", ".join([output_driver.cfg_file_names(dev)[0] for dev in devices])
                    print_err_label(dest_name)
                    _print_pre_as_diff(patching.make_pre(diff_obj), diff_args.show_rules, diff_args.indent)


def deploy(args: cli_args.DeployOptions) -> ExitCode:
    """ Сгенерировать конфиг для устройств и задеплоить его """
    ret: ExitCode = 0
    deployer = Deployer(args)
    with storage_connector.get().storage()(args) as storage:
        global live_configs  # pylint: disable=global-statement
        loader = ann_gen.Loader(storage, args)
        filterer = filtering.filterer_connector.get()
        fetcher = annet.deploy.fetcher_connector.get()
        deploy_driver = annet.deploy.driver_connector.get()
        live_configs = fetcher.fetch(devices=loader.devices, processes=args.parallel)
        pool = ann_gen.OldNewParallel(storage, args, loader, filterer)

        for res in pool.generated_configs(loader.device_ids):
            # Меняем exit code если хоть один device ловил exception
            if res.err is not None:
                ret |= 2 ** 3
            job = DeployerJob.from_device(res.device, args)
            deployer.parse_result(job, res)

        deploy_cmds = deployer.deploy_cmds
        result = annet.deploy.DeployResult(hostnames=[], results={}, durations={}, original_states={})
        if deploy_cmds:
            ans = deployer.ask_deploy()
            if ans != "y":
                return 2 ** 2
            result = annet.lib.do_async(deploy_driver.bulk_deploy(deploy_cmds, args))

        rolled_back = False
        rollback_cmds = {deployer.fqdn_to_device[x]: cc for x, cc in result.original_states.items() if cc}
        if args.rollback and rollback_cmds:
            ans = deployer.ask_rollback()
            if rollback_cmds and ans == "y":
                rolled_back = True
                annet.lib.do_async(deploy_driver.bulk_deploy(rollback_cmds, args))

        if not args.no_check_diff and not rolled_back:
            deployer.check_diff(result, storage)

        if deployer.failed_configs:
            result.add_results(deployer.failed_configs)
            ret |= 2 ** 1

        annet.deploy.show_bulk_report(result.hostnames, result.results, result.durations, log_dir=None)
        for host_result in result.results.values():
            if isinstance(host_result, Exception):
                ret |= 2 ** 0
                break
        return ret


def file_diff(args: cli_args.FileDiffOptions):
    """ Создать дифф по рулбуку между файлами или каталогами """
    old_new = list(_read_old_new_cfgdumps(args))
    pool = Parallel(file_diff_worker, args).tune_args(args)
    return pool.run(old_new, tolerate_fails=True)


def file_diff_worker(old_new: Tuple[str, str], args: cli_args.FileDiffOptions) -> Generator[
    Tuple[str, str, bool], None, None]:
    old_path, new_path = old_new
    if os.path.isdir(old_path) and os.path.isdir(new_path):
        hostname = os.path.basename(new_path)
        new_files = {relative_cfg_path: (cfg_text, "") for relative_cfg_path, cfg_text in
                     ann_gen.load_pc_config(new_path).items()}
        old_files = ann_gen.load_pc_config(old_path)
        for diff_file in _pc_diff(hostname, old_files, new_files):
            diff_text = (
                "\n".join(diff_file.diff_lines)
                if args.no_color
                else "\n".join(format_file_diff(diff_file.diff_lines))
            )
            if diff_text:
                yield diff_file.label, diff_text, False
    else:
        dest_name, old, new, hw = _read_old_new_hw(old_path, new_path, args)
        _, __, pre, ___ = _read_old_new_diff_patch(old, new, hw, add_comments=False)
        diff_lines = ann_diff.gen_pre_as_diff(pre, args.show_rules, args.indent, args.no_color)
        diff_text = "".join(diff_lines)
        if diff_text:
            yield dest_name, diff_text, False


@tracing.function
def file_patch(args: cli_args.FilePatchOptions):
    """ Создать патч между файлами или каталогами """
    old_new = list(_read_old_new_cfgdumps(args))
    pool = Parallel(file_patch_worker, args).tune_args(args)
    return pool.run(old_new, tolerate_fails=True)


def file_patch_worker(old_new: Tuple[str, str], args: cli_args.FileDiffOptions) -> Generator[
    Tuple[str, str, bool], None, None]:
    old_path, new_path = old_new
    if os.path.isdir(old_path) and os.path.isdir(new_path):
        for relative_cfg_path, cfg_text in ann_gen.load_pc_config(new_path).items():
            label = os.path.join(os.path.basename(new_path), relative_cfg_path)
            yield label, cfg_text, False
    else:
        dest_name, old, new, hw = _read_old_new_hw(old_path, new_path, args)
        _, __, ___, patch_tree = _read_old_new_diff_patch(old, new, hw, args.add_comments)
        patch_text = _format_patch_blocks(patch_tree, hw, args.indent)
        if patch_text:
            yield dest_name, patch_text, False


def _pc_diff(hostname: str, old_files: Dict[str, str], new_files: Dict[str, str]) -> Generator[PCDiffFile, None, None]:
    sorted_lines = sorted(_diff_files(old_files, new_files).items())
    for (path, (diff_lines, _reload_data, is_new)) in sorted_lines:
        if not diff_lines:
            continue
        label = hostname + os.sep + path
        if is_new:
            label = LABEL_NEW_PREFIX + label
        yield PCDiffFile(label=label, diff_lines=diff_lines)


def _json_fragment_diff(
        hostname: str,
        old_files: Dict[str, Any],
        new_files: Dict[str, Tuple[Any, Optional[str]]],
) -> Generator[PCDiffFile, None, None]:
    def jsonify_multi(files):
        return {
            path: jsontools.format_json(cfg)
            for path, cfg in files.items()
        }

    def jsonify_multi_with_cmd(files):
        ret = {}
        for path, cfg_reload_cmd in files.items():
            cfg, reload_cmd = cfg_reload_cmd
            ret[path] = (jsontools.format_json(cfg), reload_cmd)
        return ret
    jold, jnew = jsonify_multi(old_files), jsonify_multi_with_cmd(new_files)
    return _pc_diff(hostname, jold, jnew)


def guess_hw(config_text: str):
    """Пытаемся угадать вендора и hw на основе
    текста конфига и annet/rulebook/texts/*.rul"""
    scores = {}
    hw_provider = hardware_connector.get()
    for vendor in VENDOR_REVERSES:
        hw = hw_provider.vendor_to_hw(vendor)
        fmtr = tabparser.make_formatter(hw)
        rb = rulebook.get_rulebook(hw)
        config = tabparser.parse_to_tree(config_text, fmtr.split)
        pre = patching.make_pre(patching.make_diff({}, config, rb, []))
        metric = _count_pre_score(pre)
        scores[metric] = hw
    max_score = max(scores.keys())
    hw = scores[max_score]
    return hw, max_score


def _count_pre_score(top_pre) -> float:
    """Обходим вширь pre-конфиг
    и подсчитываем количество заматчившихся
    правил на каждом из уровней.

    Чем больше результирующий приоритет
    тем больше рулбук соответсвует конфигу.
    """
    score = 0
    scores = []
    cur, child = [top_pre], []
    while cur:
        for pre in cur.pop().values():
            score += 1
            for item in pre["items"].values():
                for op in [Op.ADDED, Op.AFFECTED, Op.REMOVED]:
                    child += [x["children"] for x in item[op]]
        if not cur:
            scores.append(score)
            score = 0
            cur, child = child, []
    result = 0
    for i in reversed(scores):
        result <<= i.bit_length()
        result += i
    if result > 0:
        result = 1 - (1 / result)
    return float(result)
