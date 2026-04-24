import re
import sys
from abc import ABC
from importlib import resources
from typing import Callable

from valkit.python import valid_object_path

from annet.annlib.lib import mako_render
from annet.annlib.rbparser.ordering import compile_ordering_text
from annet.annlib.rbparser.platform import VENDOR_ALIASES
from annet.connectors import CachedConnector
from annet.rulebook.deploying import compile_deploying_text
from annet.rulebook.exceptions import RulebookSyntaxError
from annet.rulebook.patching import compile_patching_text, merge_patch_rulebooks, parse_rulebook_to_text
from annet.rulebook.types import Extension, PatchingText, PatchRulebook, Rulebook
from annet.vendors import registry_connector


if sys.version_info >= (3, 12):
    from importlib.resources.abc import TraversalError

    RULEBOOK_READ_EXCEPTIONS = (FileNotFoundError, TraversalError)
else:
    RULEBOOK_READ_EXCEPTIONS = (FileNotFoundError,)


class RulebookProvider(ABC):
    def get_rulebook(self, hw) -> Rulebook:
        raise NotImplementedError


class _RulebookProviderConnector(CachedConnector[RulebookProvider]):
    name = "Rulebook provider"
    ep_name = "rulebook"


rulebook_provider_connector = _RulebookProviderConnector()


def get_rulebook(hw) -> Rulebook:
    return rulebook_provider_connector.get().get_rulebook(hw)


class DefaultRulebookProvider(RulebookProvider):
    rulebook_module = "annet.rulebook.texts"
    merge_rulebooks = {
        "rul": merge_patch_rulebooks,
    }
    compile_rulebooks: dict[Extension, Callable] = {
        "rul": compile_patching_text,
    }

    def __init__(self):
        self._rulebook_cache = {}
        self._render_rul_cache = {}
        self._escaped_rul_cache = {}
        self._rulebook_text_cache = {}

    def get_rulebook(self, hw) -> Rulebook:
        if hw in self._rulebook_cache:
            return self._rulebook_cache[hw]

        vendor = hw.vendor
        assert vendor in registry_connector.get(), "Unknown vendor: %s" % (vendor)
        rul_vendor_name = VENDOR_ALIASES.get(vendor, vendor)

        patching = self._get_rulebook_by_extension(
            # The first rulebook should be named exactly the same as hw.vendor
            rulebook_path=".".join((self.rulebook_module, rul_vendor_name)),
            vendor=rul_vendor_name,
            extension="rul",
            hw=hw,
        )
        patching_text = parse_rulebook_to_text(patching)

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

    def _get_rulebook_by_extension(self, rulebook_path: str, vendor: str, extension: Extension, hw) -> PatchRulebook:
        """Walks inheritance chain of rulebooks: gets texts → compiles → merges (if required)"""
        child_rulebook_text = self._get_rulebook_text(rulebook_path, extension, hw)
        inherit_from, child_rulebook_text = self._split_text_from_inherit_from_param(child_rulebook_text)
        child_rulebook = self.compile_rulebooks[extension](child_rulebook_text, vendor)

        if inherit_from is None:
            return child_rulebook

        parent_rulebook_path = self._parse_inherit_from_param(inherit_from)
        parent_rulebook = self._get_rulebook_by_extension(
            rulebook_path=parent_rulebook_path,
            vendor=vendor,
            extension=extension,
            hw=hw,
        )

        return self.merge_rulebooks[extension](parent_rulebook, child_rulebook, vendor)

    def _split_text_from_inherit_from_param(self, rulebook_text: str) -> tuple[str | None, str]:
        """Split the %inherit_from param from the rulebook text"""
        count_inherit_from_param = len(re.findall(r"%inherit_from", rulebook_text))
        if count_inherit_from_param == 0:
            inherit_from = None
        elif count_inherit_from_param > 1:
            raise RulebookSyntaxError(r"The rulebook must contain a single %inherit_from param.")
        elif not rulebook_text.startswith(r"%inherit_from="):
            raise RulebookSyntaxError(r"%inherit_from param must be located at the start of the file.")
        else:
            lines = rulebook_text.split("\n")
            inherit_from, rulebook_text = lines[0], "\n".join(lines[1:])
        return inherit_from, rulebook_text

    def _parse_inherit_from_param(self, param: str) -> tuple[str, str]:
        """Parses the %inherit_from param"""
        parts = param.split("=")
        if len(parts) != 2:
            raise RulebookSyntaxError(r"The %inherit_from param must follow '%inherit_from={path}' format")
        path = parts[1]
        self.check_rulebook_path(path)
        return path

    def check_rulebook_path(self, rulebook_path):
        """Validates the Python path to a rulebook"""
        if not valid_object_path(rulebook_path):
            raise ValueError(f"Invalid rulebook path '{rulebook_path}'. The path must follow the 'module.name' format.")

    def _get_rulebook_text(self, rulebook_path: str, extension: str, hw) -> PatchingText:
        """Gets the rulebook text"""
        key = (rulebook_path, extension, hw)
        if key not in self._rulebook_text_cache:
            raw_text = self._get_raw_rulebook_text(rulebook_path, extension)
            escaped_mako_text = self._escape_mako(raw_text)
            rendered_text = mako_render(escaped_mako_text, hw=hw)
            self._rulebook_text_cache[key] = re.sub(r"\n+", "\n", rendered_text.strip("\n"))
        return self._rulebook_text_cache[key]

    def _get_raw_rulebook_text(self, rulebook_path: str, extension: str):
        """Gets the raw rulebook text"""
        self.check_rulebook_path(rulebook_path)
        module, name = rulebook_path.rsplit(".", 1)
        try:
            return resources.files(module).joinpath(f"{name}.{extension}").read_text(encoding="utf-8")
        except RULEBOOK_READ_EXCEPTIONS as err:
            raise FileNotFoundError(f'Unable to find rulebook "{name}" in "{self.rulebook_module}" module') from err

    def _render_rul(self, name, hw):
        key = (name, hw)
        if key not in self._render_rul_cache:
            self._render_rul_cache[key] = mako_render(self._read_escaped_rul(name), hw=hw)
        return self._render_rul_cache[key]

    def _read_escaped_rul(self, name):
        if name in self._escaped_rul_cache:
            return self._escaped_rul_cache[name]
        try:
            text = resources.files(self.rulebook_module).joinpath(name).read_text(encoding="utf-8")
            self._escaped_rul_cache[name] = self._escape_mako(text)
            return self._escaped_rul_cache[name]
        except RULEBOOK_READ_EXCEPTIONS as err:
            raise FileNotFoundError(f"Unable to find rul: {name}") from err

    @staticmethod
    def _escape_mako(text):
        # Экранирование всего, что начинается на %, например %comment -> %%comment, чтобы он не интерпретировался
        # как mako-оператор
        text = re.sub(r"(?:^|\n)%((?!if\s*|elif\s*|else\s*|endif\s*|for\s*|endfor\s*))", "\n%%\\1", text)
        text = re.sub(r"(?:^|\n)\s*#.*", "", text)
        return text
