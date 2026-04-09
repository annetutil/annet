import re
import sys
from importlib import resources
from typing import Any, Dict, OrderedDict, TypedDict

from annet.annlib.lib import mako_render
from annet.annlib.rbparser.ordering import CompiledTree, compile_ordering_text
from annet.annlib.rbparser.platform import VENDOR_ALIASES
from annet.lib import get_context
from annet.rulebook.deploying import compile_deploying_text
from annet.rulebook.patching import compile_patching_text
from annet.vendors import registry_connector


if sys.version_info > (3, 11):
    from importlib.resources.abc import TraversalError
    RULEBOOK_READING_EXCEPTIONS = (FileNotFoundError, TraversalError)
else:
    # В Python 3.10 TraversalError отсутствует
    RULEBOOK_READING_EXCEPTIONS = (FileNotFoundError,)



DEFAULT_RULEBOOK_MODULE = "annet.rulebook.texts"


class RulebookTexts(TypedDict):
    patching: str
    ordering: str
    deploying: str


class Rulebook(TypedDict):
    patching: Dict[str, OrderedDict[str, Any]]
    ordering: CompiledTree
    deploying: OrderedDict[str, Any]
    texts: RulebookTexts


def get_rulebook(hw, rulebook_module: str | None = None) -> Rulebook:
    module = select_rulebook_module(rulebook_module)
    return RulebookProvider(module).get_rulebook(hw)


def select_rulebook_module(rulebook_module: str | None) -> str:
    if rulebook_module is not None:
        path_to_module = rulebook_module
    else:
        try:
            path_to_module = get_context()["rulebooks"]["path"]
        except KeyError:
            path_to_module = DEFAULT_RULEBOOK_MODULE
    return path_to_module


class RulebookProvider:
    def __init__(self, rulebook_module: str):
        self._rulebook_cache = {}
        self._render_rul_cache = {}
        self._escaped_rul_cache = {}
        self._rulebook_module = rulebook_module

    def get_rulebook(self, hw) -> Rulebook:
        if hw in self._rulebook_cache:
            return self._rulebook_cache[hw]

        assert hw.vendor in registry_connector.get(), "Unknown vendor: %s" % (hw.vendor)
        rul_vendor_name = VENDOR_ALIASES.get(hw.vendor, hw.vendor)

        patching_text = self._render_rul(rul_vendor_name + ".rul", hw)
        patching = compile_patching_text(patching_text, rul_vendor_name)

        try:
            ordering_text = self._render_rul(hw.vendor + ".order", hw)
        except FileNotFoundError:
            ordering_text = ""
        ordering = compile_ordering_text(ordering_text, hw.vendor)

        try:
            deploying_text = self._render_rul(hw.vendor + ".deploy", hw)
        except FileNotFoundError:
            deploying_text = ""

        deploying = compile_deploying_text(deploying_text, hw.vendor)

        self._rulebook_cache[hw] = {
            "patching": patching,
            "ordering": ordering,
            "deploying": deploying,
            "texts": {
                "patching": patching_text,
                "ordering": ordering_text,
                "deploying": deploying_text,
            },
        }
        return self._rulebook_cache[hw]

    def _render_rul(self, name, hw):
        key = (name, hw)
        if key not in self._render_rul_cache:
            self._render_rul_cache[key] = mako_render(self._read_escaped_rul(name), hw=hw)
        return self._render_rul_cache[key]

    def _read_escaped_rul(self, name):
        if name in self._escaped_rul_cache:
            return self._escaped_rul_cache[name]
        try:
            text = resources.files(self._rulebook_module).joinpath(name).read_text(encoding="utf-8")
            self._escaped_rul_cache[name] = self._escape_mako(text)
            return self._escaped_rul_cache[name]
        except RULEBOOK_READING_EXCEPTIONS as err:
            raise FileNotFoundError(f"Unable to find rul: {name}") from err

    @staticmethod
    def _escape_mako(text):
        # Экранирование всего, что начинается на %, например %comment -> %%comment, чтобы он не интерпретировался
        # как mako-оператор
        text = re.sub(r"(?:^|\n)%((?!if\s*|elif\s*|else\s*|endif\s*|for\s*|endfor\s*))", "\n%%\\1", text)
        text = re.sub(r"(?:^|\n)\s*#.*", "", text)
        return text
