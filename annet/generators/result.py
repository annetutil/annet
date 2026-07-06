from __future__ import annotations

import textwrap
from collections import OrderedDict as odict
from collections.abc import Callable, Sequence
from typing import Any

from annet.annlib import jsontools
from annet.lib import merge_dicts
from annet.reference import RefMatcher, RefTracker
from annet.types import (
    GeneratorEntireResult,
    GeneratorJSONFragmentResult,
    GeneratorPartialResult,
)


def _combine_acl_text(
    partial_results: dict[str, GeneratorPartialResult], acl_getter: Callable[[GeneratorPartialResult], str]
) -> str:
    acl_text = ""
    for gr in partial_results.values():
        for line in textwrap.dedent(acl_getter(gr)).split("\n"):
            if line and not line.isspace():
                acl_text += line.rstrip()
                acl_text += rf"  %generator_names={gr.name}"
                acl_text += "\n"
    return acl_text


class RunGeneratorResult:
    """
    Результат запуска run_partial_generators/run_file_generators
    """

    def __init__(self) -> None:
        self.partial_results: dict[str, GeneratorPartialResult] = {}
        self.entire_results: dict[str, GeneratorEntireResult] = {}
        self.json_fragment_results: dict[str, GeneratorJSONFragmentResult] = {}
        self.ref_track: RefTracker = RefTracker()
        self.ref_matcher: RefMatcher = RefMatcher()

    def add_partial(self, result: GeneratorPartialResult) -> None:
        self.partial_results[result.name] = result

    def add_entire(self, result: GeneratorEntireResult) -> None:
        # Если есть несколько генераторов на один файл, выбрать тот, что с большим приоритетом
        if result.path:
            if result.path not in self.entire_results or result.prio > self.entire_results[result.path].prio:
                self.entire_results[result.path] = result

    def add_json_fragment(self, result: GeneratorJSONFragmentResult) -> None:
        self.json_fragment_results[result.name] = result

    def config_tree(self, safe: bool = False) -> dict[str, Any]:  # OrderedDict
        tree: dict[str, Any] = odict()
        for gr in self.partial_results.values():
            config = gr.safe_config if safe else gr.config
            tree = merge_dicts(tree, config)
        return tree

    def new_files(self, safe: bool = False) -> dict[str, tuple[str, str]]:
        files: dict[str, tuple[str, str]] = {}
        for gr in self.entire_results.values():
            # add_entire only stores results whose path is truthy, so it is never None here
            assert gr.path is not None
            if not safe or gr.is_safe:
                files[gr.path] = (gr.output, gr.reload)
        return files

    def acl_text(self) -> str:
        return _combine_acl_text(self.partial_results, lambda gr: gr.acl)

    def acl_safe_text(self) -> str:
        return _combine_acl_text(self.partial_results, lambda gr: gr.acl_safe)

    def new_json_fragment_files(
        self,
        old_files: dict[str, dict[str, Any] | None],
        use_acl: bool = True,
        safe: bool = False,
        filters: Sequence[str] | None = None,
    ) -> dict[str, tuple[Any, str | None]]:
        # TODO: safe
        files: dict[str, tuple[Any, str | None]] = {}
        reload_prios: dict[str, int] = {}
        for generator_result in self.json_fragment_results.values():
            filepath = generator_result.path
            if filepath not in files:
                if old_files.get(filepath) is not None:
                    files[filepath] = (old_files[filepath], None)
                else:
                    files[filepath] = ({}, None)
            if use_acl:
                result_acl = generator_result.acl_safe if safe else generator_result.acl
            else:
                result_acl = None
            previous_config: dict[str, Any] = files[filepath][0]
            new_fragment = generator_result.config
            new_config = jsontools.apply_json_fragment(
                previous_config,
                new_fragment,
                acl=result_acl,
                filters=filters,
            )
            if jsontools.format_json(new_config) == jsontools.format_json(previous_config):
                # config is not changed, deprioritize reload_cmd
                reload_prio = 0
            else:
                reload_prio = generator_result.reload_prio

            if filepath in reload_prios and reload_prios[filepath] > reload_prio:
                _, reload_cmd = files[filepath]
            else:
                reload_cmd = generator_result.reload
                reload_prios[filepath] = reload_prio
            files[filepath] = (new_config, reload_cmd)
        return files

    def perf_mesures(self) -> dict[str, dict[str, Any]]:
        mesures: dict[str, dict[str, Any]] = {}
        for gr in self.partial_results.values():
            mesures[gr.name] = {"total": gr.perf.total, "rt": gr.perf.rt, "meta": gr.perf.meta}
        for entire_gr in self.entire_results.values():
            mesures[entire_gr.name] = {
                "total": entire_gr.perf.total,
                "rt": entire_gr.perf.rt,
                "meta": entire_gr.perf.meta,
            }
        return mesures
