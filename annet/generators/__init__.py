from __future__ import annotations

import abc
import contextlib
import dataclasses
import importlib
import os
import pkgutil
import re
import textwrap
import time
import types
from collections import OrderedDict as odict
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

from annet.annlib import jsontools
from annet.annlib.rbparser.acl import compile_acl_text
from contextlog import get_logger

from annet.storage import Device, Storage

from annet import patching, tabparser, tracing
from annet.cli_args import GenSelectOptions, ShowGeneratorsOptions
from annet.lib import (
    add_annotation,
    flatten,
    get_context,
    jinja_render,
    mako_render,
    merge_dicts,
)
from annet.reference import RefMatcher, RefTracker
from annet.tracing import tracing_connector
from annet.types import (
    GeneratorEntireResult,
    GeneratorJSONFragmentResult,
    GeneratorPartialResult,
    GeneratorPartialRunArgs,
    GeneratorPerf,
    GeneratorResult,
)


# =====
DISABLED_TAG = "disable"


# =====
class GeneratorError(Exception):
    pass


class NotSupportedDevice(GeneratorError):
    pass


class DefaultBlockIfCondition:
    pass


class GeneratorPerfMesurer:
    def __init__(
        self,
        gen: Union["PartialGenerator", "Entire"],
        storage: Storage,
        run_args: Optional[GeneratorPartialRunArgs] = None,
        trace_min_duration: tracing.MinDurationT = None
    ):
        self._gen = gen
        self._storage = storage
        self._run_args = run_args

        self._start_time: float = 0.0
        self._span_ctx = None
        self._span = None
        self._trace_min_duration = trace_min_duration

        self.last_result: Optional[GeneratorPerf] = None

    def start(self) -> None:
        self.last_result = None

        self._storage.flush_perf()

        self._span_ctx = tracing_connector.get().start_as_current_span(
            "gen:call",
            tracer_name=self._gen.__class__.__module__,
            min_duration=self._trace_min_duration,
        )
        self._span = self._span_ctx.__enter__()  # pylint: disable=unnecessary-dunder-call

        if self._span:
            self._span.set_attributes({"generator.class": self._gen.__class__.__name__})
            if self._run_args:
                tracing_connector.get().set_device_attributes(self._span, self._run_args.device)

        self._start_time = time.monotonic()

    def finish(self, exc_type=None, exc_val=None, exc_tb=None) -> GeneratorPerf:
        total = time.monotonic() - self._start_time
        rt = self._storage.flush_perf()
        self._span_ctx.__exit__(exc_type, exc_val, exc_tb)

        meta = {}
        if tracing_connector.get().enabled:
            span_context = self._span.get_span_context()
            meta = {
                "span": {
                    "trace_id": str(span_context.trace_id),
                    "span_id": str(span_context.span_id),
                }
            }

        self.last_result = GeneratorPerf(total=total, rt=rt, meta=meta)
        return self.last_result

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finish(exc_type, exc_val, exc_tb)


class RunGeneratorResult:
    """
    Результат запуска run_partial_generators/run_file_generators
    """

    def __init__(self):
        self.partial_results: Dict[str, GeneratorPartialResult] = {}
        self.entire_results: Dict[str, GeneratorEntireResult] = {}
        self.json_fragment_results: Dict[str, GeneratorJSONFragmentResult] = {}
        self.ref_track: RefTracker = RefTracker()
        self.ref_matcher: RefMatcher = RefMatcher()

    def add_partial(self, result: GeneratorPartialResult):
        self.partial_results[result.name] = result

    def add_entire(self, result: GeneratorEntireResult) -> None:
        # Если есть несколько генераторов на один файл, выбрать тот, что с большим приоритетом
        if result.path:
            if result.path not in self.entire_results or result.prio > self.entire_results[result.path].prio:
                self.entire_results[result.path] = result

    def add_json_fragment(self, result: GeneratorJSONFragmentResult) -> None:
        self.json_fragment_results[result.name] = result

    def config_tree(self, safe: bool = False) -> Dict[str, Any]:  # OrderedDict
        tree = odict()
        for gr in self.partial_results.values():
            config = gr.safe_config if safe else gr.config
            tree = merge_dicts(tree, config)
        return tree

    def new_files(self, safe: bool = False) -> Dict[str, Tuple[str, str]]:
        files = {}
        for gr in self.entire_results.values():
            if not safe or gr.is_safe:
                files[gr.path] = (gr.output, gr.reload)
        return files

    def acl_text(self) -> str:
        return _combine_acl_text(self.partial_results, lambda gr: gr.acl)

    def acl_safe_text(self) -> str:
        return _combine_acl_text(self.partial_results, lambda gr: gr.acl_safe)

    def new_json_fragment_files(
            self,
            old_files: Dict[str, Optional[str]],
            safe: bool = False,  # pylint: disable=unused-argument
    ) -> Dict[str, Tuple[Any, Optional[str]]]:
        # TODO: safe
        files: Dict[str, Tuple[Any, Optional[str]]] = {}
        reload_prios: Dict[str, int] = {}
        for generator_result in self.json_fragment_results.values():
            filepath = generator_result.path
            if filepath not in files:
                if old_files.get(filepath) is not None:
                    files[filepath] = (old_files[filepath], None)
                else:
                    files[filepath] = ({}, None)
            previous_config: Dict[str, Any] = files[filepath][0]
            new_fragment = generator_result.config
            new_config = jsontools.apply_json_fragment(previous_config, new_fragment, generator_result.acl)
            if filepath in reload_prios and reload_prios[filepath] > generator_result.reload_prio:
                _, reload_cmd = files[filepath]
            else:
                reload_cmd = generator_result.reload
                reload_prios[filepath] = generator_result.reload_prio
            files[filepath] = (new_config, reload_cmd)
        return files

    def perf_mesures(self) -> Dict[str, Dict[str, int]]:
        mesures = {}
        for gr in self.partial_results.values():
            mesures[gr.name] = {"total": gr.perf.total, "rt": gr.perf.rt, "meta": gr.perf.meta}
        for gr in self.entire_results.values():
            mesures[gr.name] = {"total": gr.perf.total, "rt": gr.perf.rt, "meta": gr.perf.meta}
        return mesures


# =====
def get_list(args: ShowGeneratorsOptions):
    if args.generators_context is not None:
        os.environ["ANN_GENERATORS_CONTEXT"] = args.generators_context
    return {
        cls.__class__.__name__: {
            "type": cls.TYPE,
            "tags": set(cls.TAGS),
            "description": get_description(cls.__class__),
        }
        for cls in _get_generators(get_context()["generators"], None)
    }


def get_description(gen_cls) -> str:
    return textwrap.dedent(" ".join([
        (gen_cls.__doc__ or ""),
        ("Disabled. Use '-g %s' to enable" % gen_cls.__name__ if DISABLED_TAG in gen_cls.TAGS else "")
    ])).strip()


def validate_genselect(gens: GenSelectOptions, all_classes):
    logger = get_logger()
    unknown_err = "Unknown generator alias %s"
    all_aliases = {
        alias
        for cls in all_classes
        for alias in cls.get_aliases()
    }
    for gen_set in (gens.allowed_gens, gens.force_enabled):
        for alias in set(gen_set or ()) - all_aliases:
            logger.error(unknown_err, alias)
            raise Exception(unknown_err % alias)


@dataclasses.dataclass
class Generators:
    """Collection of various types of generators."""

    partial: List[PartialGenerator] = dataclasses.field(default_factory=list)
    entire: List[Entire] = dataclasses.field(default_factory=list)
    json_fragment: List[JSONFragment] = dataclasses.field(default_factory=list)


def build_generators(storage, gens: GenSelectOptions, device: Optional[Device] = None) -> Generators:
    """Return generators that meet the gens filter conditions."""
    if gens.generators_context is not None:
        os.environ["ANN_GENERATORS_CONTEXT"] = gens.generators_context
    all_generators = _get_generators(get_context()["generators"], storage, device)
    validate_genselect(gens, all_generators)
    classes = list(select_generators(gens, all_generators))
    partial = [obj for obj in classes if obj.TYPE == "PARTIAL"]
    entire = [obj for obj in classes if obj.TYPE == "ENTIRE"]
    entire = list(sorted(entire, key=lambda x: x.prio, reverse=True))
    json_fragment = [obj for obj in classes if obj.TYPE == "JSON_FRAGMENT"]
    return Generators(partial=partial, entire=entire, json_fragment=json_fragment)


@tracing.function
def run_partial_initial(device, storage):
    from .common.initial import InitialConfig

    tracing_connector.get().set_device_attributes(tracing_connector.get().get_current_span(), device)

    run_args = GeneratorPartialRunArgs(device, storage)
    return run_partial_generators([InitialConfig()], run_args)


@tracing.function
def run_partial_generators(gens: List["PartialGenerator"], run_args: GeneratorPartialRunArgs):
    logger = get_logger(host=run_args.device.hostname)
    tracing_connector.get().set_device_attributes(tracing_connector.get().get_current_span(), run_args.device)

    ret = RunGeneratorResult()
    if run_args.generators_context is not None:
        os.environ["ANN_GENERATORS_CONTEXT"] = run_args.generators_context
    for gen in _get_ref_generators(get_context()["generators"], run_args.storage):
        ret.ref_matcher.add(gen.ref(run_args.device), gen.__class__)

    logger.debug("Generating selected PARTIALs ...")

    for gen in gens:
        try:
            result = _run_partial_generator(gen, run_args)
        except NotSupportedDevice:
            logger.info("generator %s is not supported for this device, skip generator for this devices!", gen)
            continue

        if not result:
            continue

        config = result.safe_config if run_args.use_acl_safe else result.config

        ref_match = ret.ref_matcher.match(config)
        for gen_cls, groups in ref_match:
            gens.append(gen_cls(run_args.storage, groups))
            ret.ref_track.add(gen.__class__, gen_cls)

        ret.ref_track.config(gen.__class__, config)
        ret.add_partial(result)

    return ret


@tracing.function(name="run_partial_generator")
def _run_partial_generator(gen: "PartialGenerator", run_args: GeneratorPartialRunArgs) -> GeneratorPartialResult:
    logger = get_logger(generator=_make_generator_ctx(gen))
    device = run_args.device
    output = ""
    config = odict()
    safe_config = odict()

    span = tracing_connector.get().get_current_span()
    if span:
        tracing_connector.get().set_device_attributes(span, run_args.device)
        tracing_connector.get().set_dimensions_attributes(span, gen, run_args.device)
        span.set_attributes({
            "use_acl": run_args.use_acl,
            "use_acl_safe": run_args.use_acl_safe,
            "generators_context": str(run_args.generators_context),
        })

    with GeneratorPerfMesurer(gen, run_args.storage, run_args=run_args) as pm:
        if not run_args.no_new:
            if gen.get_user_runner(device):
                logger.info("Generating PARTIAL ...")
            try:
                output = gen(device, run_args.annotate)
            except NotSupportedDevice:
                # это исключение нужно передать выше в оригинальном виде
                raise
            except Exception as err:
                filename, lineno = gen.get_running_line()
                logger.exception("Generator error in file '%s:%i'", filename, lineno)
                raise GeneratorError(f"{gen} on {device}") from err

            fmtr = tabparser.make_formatter(device.hw)
            try:
                config = tabparser.parse_to_tree(text=output, splitter=fmtr.split)
            except tabparser.ParserError as err:
                logger.exception("Parser error")
                raise GeneratorError from err

    acl = gen.acl(device) or ""
    rules = compile_acl_text(textwrap.dedent(acl), device.hw.vendor)
    acl_safe = gen.acl_safe(device) or ""
    safe_rules = compile_acl_text(textwrap.dedent(acl_safe), device.hw.vendor)

    if run_args.use_acl:
        try:
            with tracing_connector.get().start_as_current_span("apply_acl", tracer_name=__name__, min_duration="0.01") as acl_span:
                tracing_connector.get().set_device_attributes(acl_span, run_args.device)
                config = patching.apply_acl(
                    config=config,
                    rules=rules,
                    fatal_acl=True,
                    with_annotations=run_args.annotate,
                )
            if run_args.use_acl_safe:
                with tracing_connector.get().start_as_current_span(
                    "apply_acl_safe",
                    tracer_name=__name__,
                    min_duration="0.01"
                ) as acl_safe_span:
                    tracing_connector.get().set_device_attributes(acl_safe_span, run_args.device)
                    safe_config = patching.apply_acl(
                        config=config,
                        rules=safe_rules,
                        fatal_acl=False,
                        with_annotations=run_args.annotate,
                    )
        except patching.AclError as err:
            logger.error("ACL error: generator is not allowed to yield this command: %s", err)
            raise GeneratorError from err
        except NotImplementedError as err:
            logger.error(str(err))
            raise GeneratorError from err

    return GeneratorPartialResult(
        name=gen.__class__.__name__,
        tags=gen.TAGS,
        output=output,
        acl=acl,
        acl_rules=rules,
        acl_safe=acl_safe,
        acl_safe_rules=safe_rules,
        config=config,
        safe_config=safe_config,
        perf=pm.last_result,
    )


@tracing.function
def check_entire_generators_required_packages(gens, device_packages: FrozenSet[str]) -> List[str]:
    errors: List[str] = []
    for gen in gens:
        if not gen.REQUIRED_PACKAGES.issubset(device_packages):
            missing = gen.REQUIRED_PACKAGES - device_packages
            missing_str = ", ".join("`{}'".format(pkg) for pkg in sorted(missing))
            if len(missing) == 1:
                errors.append("missing package {} required for {}".format(missing_str, gen))
            else:
                errors.append("missing packages {} required for {}".format(missing_str, gen))
    return errors


@tracing.function
def run_file_generators(
        gens: Iterable[Union["JSONFragment", "Entire"]],
        device: "Device",
        storage: Storage,
) -> RunGeneratorResult:
    """Run generators that generate files or file parts."""
    ret = RunGeneratorResult()
    logger = get_logger(host=device.hostname)
    logger.debug("Generating selected ENTIREs and JSON_FRAGMENTs ...")
    for gen in gens:
        if gen.__class__.TYPE == "ENTIRE":
            run_generator_fn = _run_entire_generator
            add_result_fn = ret.add_entire
        elif gen.__class__.TYPE == "JSON_FRAGMENT":
            run_generator_fn = _run_json_fragment_generator
            add_result_fn = ret.add_json_fragment
        else:
            raise RuntimeError(f"Unknown generator class type: cls={gen.__class__} TYPE={gen.__class__.TYPE}")
        try:
            result = run_generator_fn(gen, device, storage)
        except NotSupportedDevice:
            logger.info("generator %s is not supported for this device", gen)
            continue
        if result:
            add_result_fn(result)

    return ret


@tracing.function(min_duration="0.5")
def _run_entire_generator(gen: "Entire", device: "Device", storage: Storage) -> Optional[GeneratorResult]:
    span = tracing_connector.get().get_current_span()
    if span:
        tracing_connector.get().set_device_attributes(span, device)
        tracing_connector.get().set_dimensions_attributes(span, gen, device)

    logger = get_logger(generator=_make_generator_ctx(gen))
    path = gen.path(device)
    if path:
        logger.info("Generating ENTIRE ...")

        with GeneratorPerfMesurer(gen, storage, trace_min_duration="0.5") as pm:
            output = gen(device)

        reload_cmds = gen.get_reload_cmds(device)
        prio = gen.prio

        return GeneratorEntireResult(
            name=gen.__class__.__name__,
            tags=gen.TAGS,
            path=path,
            output=output,
            reload=reload_cmds,
            prio=prio,
            perf=pm.last_result,
            is_safe=gen.is_safe(device),
        )
    return None


def _make_generator_ctx(gen):
    return "%s.[%s]" % (gen.__module__, gen.__class__.__name__)


def _run_json_fragment_generator(
        gen: "JSONFragment",
        device: "Device",
        storage: Storage,
) -> Optional[GeneratorResult]:
    logger = get_logger(generator=_make_generator_ctx(gen))
    path = gen.path(device)

    acl_item_or_list_of_items = gen.acl(device)
    if isinstance(acl_item_or_list_of_items, list):
        acl = acl_item_or_list_of_items
    else:
        acl = [acl_item_or_list_of_items]

    if path:
        logger.info("Generating JSON_FRAGMENT ...")

        with GeneratorPerfMesurer(gen, storage) as pm:
            config = gen(device)

        reload_cmds = gen.get_reload_cmds(device)

        return GeneratorJSONFragmentResult(
            name=gen.__class__.__name__,
            tags=gen.TAGS,
            path=path,
            acl=acl,
            config=config,
            reload=reload_cmds,
            perf=pm.last_result,
            is_safe=gen.is_safe(device),
            reload_prio=gen.reload_prio,
        )
    return None


def _get_generators(module_paths: Union[List[str], dict], storage, device=None):
    if isinstance(module_paths, dict):
        if device is None:
            module_paths = module_paths.get("default")
        else:
            modules = []
            seen = set()
            for prop, prop_modules in module_paths.get("per_device_property", {}).items():
                if getattr(device, prop, False) is True:
                    for module in prop_modules:
                        if module not in seen:
                            modules.append(module)
                            seen.add(module)
            module_paths = modules or module_paths.get("default")
    res_generators = []
    for module_path in module_paths:
        module = importlib.import_module(module_path)
        if hasattr(module, "get_generators"):
            generators: List[BaseGenerator] = module.get_generators(storage)
            res_generators += generators
    return res_generators


def _get_ref_generators(module_paths: List[str], storage):
    if isinstance(module_paths, dict):
        module_paths = module_paths.get("default")
    res_generators = []
    for module_path in module_paths:
        module = importlib.import_module(module_path)
        if hasattr(module, "get_ref_generators"):
            res_generators += module.get_ref_generators(storage)
    return res_generators


class InvalidValueFromGenerator(ValueError):
    pass


class GenStringable(abc.ABC):
    @abc.abstractmethod
    def gen_str(self) -> str:
        pass


ParamsList = tabparser.JuniperList


def _filter_str(value: Union[str, int, float, tabparser.JuniperList, ParamsList, GenStringable]):
    if isinstance(value, (
        str,
        int,
        float,
        tabparser.JuniperList,
        ParamsList,
    )):
        return str(value)

    if hasattr(value, "gen_str") and callable(value.gen_str):
        return value.gen_str()

    raise InvalidValueFromGenerator("Invalid yield type: %s(%s)" % (type(value).__name__, value))


# =====
class BaseGenerator:
    TYPE: str
    TAGS: list[str]

    def supports_vendor(self, vendor: str) -> bool:  # pylint: disable=unused-argument
        return True


class TreeGenerator(BaseGenerator):
    def __init__(self, indent="  "):
        self._indents = []
        self._rows = []
        self._block_path = []
        self._indent = indent

    @tracing.contextmanager(min_duration="0.1")
    @contextlib.contextmanager
    def block(self, *tokens, indent=None):
        span = tracing_connector.get().get_current_span()
        if span:
            span.set_attribute("tokens", " ".join(map(str, tokens)))

        indent = self._indent if indent is None else indent
        block = " ".join(map(_filter_str, tokens))
        self._block_path.append(block)
        self._append_text(block)
        self._indents.append(indent)
        yield
        self._indents.pop(-1)
        self._block_path.pop(-1)

    @contextlib.contextmanager
    def block_if(self, *tokens, condition=DefaultBlockIfCondition):
        if condition is DefaultBlockIfCondition:
            condition = (None not in tokens and "" not in tokens)
        if condition:
            with self.block(*tokens):
                yield
                return
        yield

    @contextlib.contextmanager
    def multiblock(self, *blocks):
        if blocks:
            blk = blocks[0]
            tokens = blk if isinstance(blk, (list, tuple)) else [blk]
            with self.block(*tokens):
                with self.multiblock(*blocks[1:]):
                    yield
                    return
        yield

    @contextlib.contextmanager
    def multiblock_if(self, *blocks, condition=DefaultBlockIfCondition):
        if condition is DefaultBlockIfCondition:
            condition = (None not in blocks)
            if condition:
                if blocks:
                    blk = blocks[0]
                    tokens = blk if isinstance(blk, (list, tuple)) else [blk]
                    with self.block(*tokens):
                        with self.multiblock(*blocks[1:]):
                            yield
                            return
        yield

    # ===
    def _append_text(self, text):
        self._append_text_cb(text)

    def _append_text_cb(self, text, row_cb=None):
        for row in _split_and_strip(text):
            if row_cb:
                row = row_cb(row)
            self._rows.append("".join(self._indents) + row)


class TextGenerator(TreeGenerator):
    def __add__(self, line):
        self._append_text(line)
        return self

    def __iter__(self):
        yield from self._rows


class PartialGenerator(TreeGenerator):
    TYPE = "PARTIAL"
    TAGS: List[str] = []

    def __init__(self, storage):
        super().__init__()
        self.storage = storage
        self._annotate = False
        self._running_gen = None
        self._annotations = []
        self._annotation_module = self.__class__.__module__ or ""

    def supports_vendor(self, vendor: str) -> bool:
        if self.__class__.run is PartialGenerator.run:
            return hasattr(self, f"run_{vendor}")
        else:
            return True

    def acl(self, device):
        if hasattr(self, "acl_" + device.hw.vendor):
            return getattr(self, "acl_" + device.hw.vendor)(device)

    def acl_safe(self, device):
        if hasattr(self, "acl_safe_" + device.hw.vendor):
            return getattr(self, "acl_safe_" + device.hw.vendor)(device)

    def run(self, device) -> Iterable[Union[str, tuple]]:
        if hasattr(self, "run_" + device.hw.vendor):
            return getattr(self, "run_" + device.hw.vendor)(device)
        logger = get_logger()
        logger.info(
            "generator %s is not supported for vendor %s",
            self,
            device.hw.vendor,
        )
        return iter(())

    def get_user_runner(self, device):
        if self.__class__.run is not PartialGenerator.run:
            return self.run
        elif hasattr(self, "run_" + device.hw.vendor):
            return getattr(self, "run_" + device.hw.vendor)
        return None

    # =====

    @classmethod
    def get_aliases(cls) -> Set[str]:
        return {cls.__name__, *cls.TAGS}

    def __call__(self, device, annotate=False):
        self._indents = []
        self._rows = []
        self._running_gen = self.run(device)
        self._annotate = annotate

        if annotate and self.__class__.__module__:
            self._annotation_module = ".".join(self.__class__.__module__.split(".")[-2:])

        for text in self._running_gen:
            if isinstance(text, tuple):
                text = " ".join(map(_filter_str, flatten(text)))
            else:
                text = _filter_str(text)
            self._append_text(text)

        for row in self._rows:
            assert re.search(r"\bNone\b", row) is None, "Found 'None' in yield result: %s" % (row)
        if annotate:
            generated_rows = (add_annotation(x, y) for (x, y) in zip(self._rows, self._annotations))
        else:
            generated_rows = self._rows
        return "\n".join(generated_rows) + "\n"

    def _append_text(self, text):
        def annotation_cb(row):
            annotation = "%s:%d" % self.get_running_line()
            self._annotations.append(annotation)
            return row

        self._append_text_cb(
            text,
            annotation_cb if self._annotate else None
        )

    def get_running_line(self):
        if not self._running_gen or not self._running_gen.gi_frame:
            return (repr(self._running_gen), -1)
        return self._annotation_module, self._running_gen.gi_frame.f_lineno

    @classmethod
    def literal(cls, item):
        return '"{}"'.format(item)

    def __repr__(self):
        return "<%s>" % self.__class__.__name__


class RefGenerator(PartialGenerator):
    def __init__(self, storage, groups=None):
        super().__init__(storage)
        self.groups = groups

    def ref(self, device):
        if hasattr(self, "ref_" + device.hw.vendor):
            return getattr(self, "ref_" + device.hw.vendor)(device)
        return ""


class Entire(BaseGenerator):
    TYPE = "ENTIRE"
    TAGS: List[str] = []
    REQUIRED_PACKAGES: FrozenSet[str] = frozenset()

    def __init__(self, storage):
        self.storage = storage
        # между генераторами для одного и того же path - выбирается тот что больше
        if not hasattr(self, "prio"):
            self.prio = 100
        self.__device = None

    def run(self, device) -> Union[None, str, Iterable[Union[str, tuple]]]:
        raise NotImplementedError

    def reload(self, device) -> Optional[str]:  # pylint: disable=unused-argument
        return

    def get_reload_cmds(self, device) -> str:
        ret = self.reload(device) or ""
        path = self.path(device)
        if path and device.hw.PC and device.hw.soft.startswith(("Cumulus", "SwitchDev", "SONiC")):
            parts = []
            if ret:
                parts.append(ret)
            parts.append("/usr/bin/etckeeper commitreload %s" % path)
            return "\n".join(parts)
        return ret

    def path(self, device) -> Optional[str]:
        raise NotImplementedError("Required PATH for ENTIRE generator")

    # pylint: disable=unused-argument
    def is_safe(self, device) -> bool:
        """Output gen results when --acl-safe flag is used"""
        return False

    def read(self, path) -> str:
        return pkgutil.get_data(__name__, path).decode()

    def mako(self, text, **kwargs) -> str:
        return mako_render(text, dedent=True, device=self.__device, **kwargs)

    def jinja(self, text, **kwargs) -> str:
        return jinja_render(text, dedent=True, device=self.__device, **kwargs)

    # =====

    @classmethod
    def get_aliases(cls) -> Set[str]:
        return {cls.__name__, *cls.TAGS}

    def __call__(self, device):
        self.__device = device
        parts = []
        run_res = self.run(device)
        if isinstance(run_res, str):
            run_res = (run_res,)
        if run_res is None or not isinstance(run_res, (tuple, types.GeneratorType)):
            raise Exception("generator %s returns %s" % (self.__class__.__name__, type(run_res)))
        for text in run_res:
            if isinstance(text, tuple):
                text = " ".join(map(_filter_str, flatten(text)))
            assert re.search(r"\bNone\b", text) is None, "Found 'None' in yield result: %s" % text
            parts.append(text)
        return "\n".join(parts)


def select_generators(gens: GenSelectOptions, classes: Iterable[BaseGenerator]):
    def contains(obj, where):
        if where:
            return obj.get_aliases().intersection(where)
        return False

    def has(cls, what):
        return what in cls.TAGS

    flts = [lambda c: not isinstance(c, RefGenerator)]
    if gens.allowed_gens:
        flts.append(lambda c: contains(c, gens.allowed_gens))
    elif gens.force_enabled:
        flts.append(lambda c: not has(c, DISABLED_TAG) or contains(c, gens.force_enabled))
    elif not gens.ignore_disabled:
        flts.append(lambda c: not has(c, DISABLED_TAG))

    if gens.excluded_gens:
        flts.append(lambda c: not contains(c, gens.excluded_gens))

    return filter(lambda x: all(f(x) for f in flts), classes)


def _split_and_strip(text):
    if "\n" in text:
        rows = textwrap.dedent(text).strip().split("\n")
    else:
        rows = [text]
    return rows


def _combine_acl_text(
    partial_results: Dict[str, GeneratorPartialResult],
    acl_getter: Callable[[GeneratorPartialResult], str]
) -> str:
    acl_text = ""
    for gr in partial_results.values():
        for line in textwrap.dedent(acl_getter(gr)).split("\n"):
            if line and not line.isspace():
                acl_text += line.rstrip()
                acl_text += fr"  %generator_names={gr.name}"
                acl_text += "\n"
    return acl_text


class JSONFragment(TreeGenerator):
    """Generates parts of JSON config file."""

    TYPE = "JSON_FRAGMENT"
    TAGS: List[str] = []

    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage
        self._json_config: Dict[str, Any] = {}
        self._config_pointer: List[str] = []

        # if two generators edit same file, commands from generator with greater `reload_prio` will be used
        if not hasattr(self, "reload_prio"):
            self.reload_prio = 100

    def path(self, device: Device) -> Optional[str]:
        raise NotImplementedError("Required PATH for JSON_FRAGMENT generator")

    @classmethod
    def get_aliases(cls) -> Set[str]:
        return {cls.__name__, *cls.TAGS}

    def acl(self, device: Device) -> Union[str, List[str]]:
        """
        Restrict the generator to a specified ACL using JSON Pointer syntax.

        Expected ACL to be a list of strings, but a single string is also allowed.
        """
        raise NotImplementedError("Required ACL for JSON_FRAGMENT generator")

    def run(self, device: Device):
        raise NotImplementedError

    # pylint: disable=unused-argument
    def is_safe(self, device: Device) -> bool:
        """Output gen results when --acl-safe flag is used"""
        return False

    def get_reload_cmds(self, device: Device) -> str:
        ret = self.reload(device) or ""
        return ret

    def reload(self, device) -> Optional[str]:
        raise NotImplementedError

    @contextlib.contextmanager
    def block(self, *tokens, indent=None):  # pylint: disable=unused-argument
        block_str = "".join(map(_filter_str, tokens))
        self._config_pointer.append(block_str)
        try:
            yield
        finally:
            self._config_pointer.pop()

    @contextlib.contextmanager
    def block_piped(self, *tokens, indent=None):  # pylint: disable=unused-argument
        block_str = "|".join(map(_filter_str, tokens))
        self._config_pointer.append(block_str)
        try:
            yield
        finally:
            self._config_pointer.pop()

    def __call__(self, device: Device, annotate: bool = False):
        for cfg_fragment in self.run(device):
            self._set_or_replace_dict(self._config_pointer, cfg_fragment)
        return self._json_config

    def _set_or_replace_dict(self, pointer, value):
        if not pointer:
            if self._json_config == {}:
                self._json_config = value
            else:
                self._json_config = [self._json_config, value]
        else:
            self._set_dict(self._json_config, pointer, value)

    @classmethod
    def _to_str(cls, value: Any) -> str:
        if isinstance(value, str):
            return value
        elif isinstance(value, list):
            return [cls._to_str(x) for x in value]
        elif isinstance(value, dict):
            for k, v in value.items():
                value[k] = cls._to_str(v)
            return value
        return str(value)

    @classmethod
    def _set_dict(cls, cfg, pointer, value):
        # pointer has at least one key
        if len(pointer) == 1:
            if pointer[0] in cfg:
                cfg[pointer[0]] = [cfg[pointer[0]], cls._to_str(value)]
            else:
                cfg[pointer[0]] = cls._to_str(value)
        else:
            if pointer[0] not in cfg:
                cfg[pointer[0]] = {}
            cls._set_dict(cfg[pointer[0]], pointer[1:], cls._to_str(value))
