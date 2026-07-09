from __future__ import annotations

from collections import OrderedDict
from collections.abc import MutableMapping
from typing import Any, NamedTuple, TypeAlias, cast

from annet.annlib.jsontools import JsonFragmentAcl
from annet.annlib.types import Op as Op  # pylint: disable=unused-import
from annet.annlib.types import OpType as OpType  # pylint: disable=unused-import
from annet.storage import Device, Storage


class PCDiffFile(NamedTuple):
    label: str
    diff_lines: list[str]


class PCDiff(NamedTuple):
    hostname: str
    diff_files: list[PCDiffFile]


DiffItem: TypeAlias = tuple[OpType, str, "Diff", dict[Any, Any]]
Diff: TypeAlias = list[DiffItem]
ExitCode: TypeAlias = int


class GeneratorPerf:
    """
    Рантайм статистика времени выполнения генератора
    """

    def __init__(self, total: float, rt: dict[str, list[dict[str, Any]]] | None, meta: dict[str, Any] | None = None):
        self.total = total
        self.rt = rt
        self._meta = meta

    @property
    def meta(self) -> dict[str, Any]:
        return self._meta or {}


class GeneratorPartialRunArgs:
    """
    Параметры и модификаторы для запуска run_partial_generators
    """

    def __init__(
        self,
        device: Device,
        use_acl: bool = False,
        use_acl_safe: bool = False,
        annotate: bool = False,
        generators_context: str | None = None,
        no_new: bool = False,
    ):
        self.device = device
        self.use_acl = use_acl  # фильтруем по acl ввыод генератора (--no-acl для дебага)
        self.use_acl_safe = use_acl_safe  # [NOCDEV-6190] используем более строгий генераторный acl
        self.annotate = annotate  # добавляем в каждую строку вывода информацию откуда она была заyield'ена
        self.generators_context = generators_context  # строка с именем контекста генераторов
        self.no_new = no_new  # для опции --clear, не пытаемся запустить генераторы, выдаем только acl


class GeneratorPartialResult:
    """
    Результат запуска Partial-генератора
    """

    def __init__(
        self,
        name: str,
        tags: list[str],
        acl: str,
        acl_rules: dict[str, OrderedDict[Any, Any]],
        acl_safe: str,
        acl_safe_rules: dict[str, OrderedDict[Any, Any]],
        output: str,
        config: OrderedDict[str, Any],
        safe_config: OrderedDict[str, Any],
        perf: GeneratorPerf,
    ):
        self.name = name
        self.tags = tags
        self.acl = acl
        self.acl_rules = acl_rules
        self.acl_safe = acl_safe
        self.acl_safe_rules = acl_safe_rules
        self.output = output
        self.config = config
        self.safe_config = safe_config
        self.perf = perf


class GeneratorEntireResult:
    """
    Результат запуска Entire-генератора
    """

    def __init__(
        self,
        name: str,
        tags: list[str],
        path: str | None,
        output: str,
        reload: str,
        prio: int,
        perf: GeneratorPerf,
        is_safe: bool,
    ):
        self.name = name
        self.tags = tags
        self.path = path
        self.output = output
        self.reload = reload
        self.prio = prio
        self.perf = perf
        self.is_safe = is_safe


class GeneratorJSONFragmentResult:
    """
    Результат запуска JSONFragment-генератора
    """

    def __init__(
        self,
        name: str,
        tags: list[str],
        path: str,
        acl: list[JsonFragmentAcl],
        acl_safe: list[JsonFragmentAcl],
        config: dict[str, Any],
        reload: str,
        perf: GeneratorPerf,
        reload_prio: int,
    ):
        self.name = name
        self.tags = tags
        self.path = path
        self.acl = acl
        self.acl_safe = acl_safe
        self.config = config
        self.reload = reload
        self.perf = perf
        self.reload_prio = reload_prio


GeneratorResult = GeneratorEntireResult | GeneratorPartialResult | GeneratorJSONFragmentResult


class OldNewResult:
    """Результат запуска old_new"""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        device: Device | None = None,
        old: MutableMapping[str, Any] | None = None,
        new: MutableMapping[str, Any] | None = None,
        acl_rules: MutableMapping[str, Any] | None = None,
        new_files: MutableMapping[str, tuple[str, str]] | None = None,
        old_files: MutableMapping[str, str | None] | None = None,
        err: Exception | None = None,
        partial_result: dict[str, GeneratorPartialResult] | None = None,
        entire_result: dict[str, GeneratorEntireResult] | None = None,
        old_json_fragment_files: dict[str, Any] | None = None,
        new_json_fragment_files: dict[str, tuple[Any, str | None]] | None = None,
        json_fragment_result: dict[str, GeneratorJSONFragmentResult] | None = None,
        implicit_rules: dict[str, Any] | None = None,
        perf: dict[str, dict[str, float]] | None = None,
        acl_safe_rules: MutableMapping[str, Any] | None = None,
        safe_old: MutableMapping[str, Any] | None = None,
        safe_new: MutableMapping[str, Any] | None = None,
        safe_new_files: MutableMapping[str, tuple[str, str]] | None = None,
        safe_new_json_fragment_files: dict[str, tuple[Any, str | None]] | None = None,
        filter_acl_rules: MutableMapping[str, Any] | None = None,
    ) -> None:
        self.device: Device = cast(Device, device)
        self.old: MutableMapping[str, Any] = old if old else OrderedDict()
        self.new: MutableMapping[str, Any] = new if new else OrderedDict()
        self.acl_rules: MutableMapping[str, Any] = cast(MutableMapping[str, Any], acl_rules)
        self.new_files: MutableMapping[str, tuple[str, str]] = new_files if new_files else {}
        self.old_files: MutableMapping[str, str | None] = old_files if old_files else {}
        self.err: Exception | None = err
        self.partial_results: dict[str, GeneratorPartialResult] = partial_result or {}
        self.entire_results: dict[str, GeneratorEntireResult] = entire_result or {}
        self.old_json_fragment_files: dict[str, Any] = old_json_fragment_files or {}
        self.new_json_fragment_files: dict[str, tuple[Any, str | None]] = new_json_fragment_files or {}
        self.json_fragment_results: dict[str, GeneratorJSONFragmentResult] = json_fragment_result or {}
        self.implicit_rules: dict[str, Any] = implicit_rules or OrderedDict()
        self.perf: dict[str, dict[str, float]] = perf or {}

        # safe acl and configs with it applied
        self.acl_safe_rules: MutableMapping[str, Any] = acl_safe_rules or {}
        self.safe_old: MutableMapping[str, Any] = safe_old if safe_old else OrderedDict()
        self.safe_new: MutableMapping[str, Any] = safe_new if safe_new else OrderedDict()
        self.safe_new_files: MutableMapping[str, tuple[str, str]] = safe_new_files if safe_new_files else {}
        self.safe_new_json_fragment_files: dict[str, tuple[Any, str | None]] = safe_new_json_fragment_files or {}

        self.filter_acl_rules: MutableMapping[str, Any] | None = filter_acl_rules

    def get_old(self, safe: bool = False) -> MutableMapping[str, Any]:
        if safe:
            return self.safe_old

        return self.old

    def get_new(self, safe: bool = False) -> MutableMapping[str, Any]:
        if safe:
            return self.safe_new

        return self.new

    def get_acl_rules(self, safe: bool = False) -> MutableMapping[str, Any]:
        if safe:
            return self.acl_safe_rules

        return self.acl_rules

    def get_new_files(self, safe: bool = False) -> MutableMapping[str, tuple[str, str]]:
        if safe:
            return self.safe_new_files

        return self.new_files

    def get_new_file_fragments(self, safe: bool = False) -> dict[str, tuple[Any, str | None]]:
        if safe:
            return self.safe_new_json_fragment_files

        return self.new_json_fragment_files
