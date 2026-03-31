from importlib import import_module
import os
import re
from typing import Any, Dict, OrderedDict, TypedDict

from annet.annlib.lib import mako_render
from annet.annlib.rbparser.ordering import CompiledTree, compile_ordering_text
from annet.annlib.rbparser.platform import VENDOR_ALIASES
from annet.lib import get_context
from annet.rulebook.deploying import compile_deploying_text
from annet.rulebook.patching import compile_patching_text
from annet.vendors import registry_connector


class RulebookTexts(TypedDict):
    patching: str
    ordering: str
    deploying: str


class Rulebook(TypedDict):
    patching: Dict[str, OrderedDict[str, Any]]
    ordering: CompiledTree
    deploying: OrderedDict[str, Any]
    texts: RulebookTexts


def get_rulebook(hw) -> Rulebook:
    return RulebookProvider().get_rulebook(hw)


class RulebookProvider:
    def __init__(self):
        self._rulebook_cache = {}
        self._render_rul_cache = {}
        self._escaped_rul_cache = {}

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
        python_path_to_module = get_context().get("rulebook_module")
        module = import_module(python_path_to_module)
        if module.__file__ is None:
            raise ModuleNotFoundError(f"File __init__.py missing from the {python_path_to_module} module.")
        path_to_rulebook_dir = os.path.dirname(module.__file__)
        try:
            with open(os.path.join(path_to_rulebook_dir, name), "r", encoding="utf-8") as f:
                self._escaped_rul_cache[name] = self._escape_mako(f.read())
                return self._escaped_rul_cache[name]
        except FileNotFoundError:
            raise FileNotFoundError(f"Unable to find rul: {name}")

    @staticmethod
    def _escape_mako(text):
        # Экранирование всего, что начинается на %, например %comment -> %%comment, чтобы он не интерпретировался
        # как mako-оператор
        text = re.sub(r"(?:^|\n)%((?!if\s*|elif\s*|else\s*|endif\s*|for\s*|endfor\s*))", "\n%%\\1", text)
        text = re.sub(r"(?:^|\n)\s*#.*", "", text)
        return text
