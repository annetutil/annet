import re
import sys
from abc import ABC
from collections import OrderedDict
from collections.abc import Callable
from importlib import resources
from typing import Literal, cast, overload

from valkit.python import valid_object_path

from annet.annlib.lib import mako_render
from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.rbparser.exceptions import RulebookSyntaxError
from annet.annlib.rbparser.ordering import compile_ordering_text, dump_order_rulebook, merge_order_rulebooks
from annet.annlib.rbparser.platform import VENDOR_ALIASES
from annet.connectors import CachedConnector
from annet.lib import get_context
from annet.rulebook.deploying import compile_deploying_text, dump_deploy_rulebook, merge_deploy_rulebooks
from annet.rulebook.patching import compile_patching_text, dump_patch_rulebook, merge_patch_rulebooks
from annet.rulebook.types import (
    AnyRulebook as AnyRulebook,
)
from annet.rulebook.types import (
    AnyRulebookText as AnyRulebookText,
)
from annet.rulebook.types import (
    DeployingText as DeployingText,
)
from annet.rulebook.types import (
    DeployRulebook as DeployRulebook,
)
from annet.rulebook.types import (
    Extension as Extension,
)
from annet.rulebook.types import (
    OrderingText as OrderingText,
)
from annet.rulebook.types import (
    OrderRulebook as OrderRulebook,
)
from annet.rulebook.types import (
    PatchingText as PatchingText,
)
from annet.rulebook.types import (
    PatchRulebook as PatchRulebook,
)
from annet.rulebook.types import (
    Rulebook as Rulebook,
)
from annet.rulebook.types import (
    RulebookTexts as RulebookTexts,
)
from annet.vendors import registry_connector


RULEBOOK_READ_EXCEPTIONS: tuple[type[BaseException], ...] = (FileNotFoundError,)
if sys.version_info >= (3, 12):
    # importlib.resources.abc.TraversalError exists at runtime on 3.12+, but is missing
    # from the typeshed stubs for 3.13/3.14; look it up dynamically so this module both
    # type-checks on those versions and still catches the error when it is available.
    from importlib.resources import abc as _resources_abc

    _traversal_error = cast("type[BaseException] | None", getattr(_resources_abc, "TraversalError", None))
    if _traversal_error is not None:
        RULEBOOK_READ_EXCEPTIONS = (FileNotFoundError, _traversal_error)


RUL: Literal["rul"] = "rul"
ORDER: Literal["order"] = "order"
DEPLOY: Literal["deploy"] = "deploy"


class RulebookProvider(ABC):
    def get_rulebook(self, hw: HardwareView) -> Rulebook:
        raise NotImplementedError


class _RulebookProviderConnector(CachedConnector[RulebookProvider]):
    name = "Rulebook provider"
    ep_name = "rulebook"


rulebook_provider_connector = _RulebookProviderConnector()


def get_rulebook(hw: HardwareView) -> Rulebook:
    return rulebook_provider_connector.get().get_rulebook(hw)


class DefaultRulebookProvider(RulebookProvider):
    DEFAULT_RULEBOOK_MODULE = "annet.rulebook.texts"
    merge_rulebooks: dict[Extension, Callable[..., AnyRulebook]] = {
        RUL: merge_patch_rulebooks,
        ORDER: merge_order_rulebooks,
        DEPLOY: merge_deploy_rulebooks,
    }
    compile_rulebooks: dict[Extension, Callable[..., AnyRulebook]] = {
        RUL: compile_patching_text,
        ORDER: compile_ordering_text,
        DEPLOY: compile_deploying_text,
    }

    def __init__(self) -> None:
        try:
            context_module = get_context().get("rulebook", {}).get("module")
        except FileNotFoundError:
            context_module = None
        self.rulebook_module = context_module or self.DEFAULT_RULEBOOK_MODULE
        self._rulebook_cache: dict[HardwareView, Rulebook] = {}
        self._rulebook_text_cache: dict[tuple[str, Extension, HardwareView], AnyRulebookText] = {}

    def get_rulebook(self, hw: HardwareView) -> Rulebook:
        if hw in self._rulebook_cache:
            return self._rulebook_cache[hw]

        vendor = hw.vendor
        assert vendor is not None and vendor in registry_connector.get(), "Unknown vendor: %s" % (vendor)
        rul_vendor_name = VENDOR_ALIASES.get(vendor, vendor)

        patching: PatchRulebook = self._get_rulebook_by_extension(
            # The first rulebook should be named exactly the same as hw.vendor
            rulebook_path=".".join((self.rulebook_module, rul_vendor_name)),
            vendor=rul_vendor_name,
            extension=RUL,
            hw=hw,
        )
        patching_text: PatchingText = dump_patch_rulebook(patching)

        ordering: OrderRulebook
        ordering_text: OrderingText
        try:
            ordering = self._get_rulebook_by_extension(
                rulebook_path=".".join((self.rulebook_module, vendor)),
                vendor=vendor,
                extension=ORDER,
                hw=hw,
            )
            ordering_text = dump_order_rulebook(ordering)
        except FileNotFoundError:
            ordering = []
            ordering_text = ""

        deploying: DeployRulebook
        deploying_text: DeployingText
        try:
            deploying = self._get_rulebook_by_extension(
                rulebook_path=".".join((self.rulebook_module, vendor)),
                vendor=vendor,
                extension=DEPLOY,
                hw=hw,
            )
            deploying_text = dump_deploy_rulebook(deploying)
        except FileNotFoundError:
            deploying = OrderedDict()
            deploying_text = ""

        self._rulebook_cache[hw] = Rulebook(
            patching=patching,
            ordering=ordering,
            deploying=deploying,
            texts=RulebookTexts(
                patching=patching_text,
                ordering=ordering_text,
                deploying=deploying_text,
            ),
        )
        return self._rulebook_cache[hw]

    @overload
    def _get_rulebook_by_extension(  # noqa: E704
        self, rulebook_path: str, vendor: str, extension: Literal["rul"], hw: HardwareView
    ) -> PatchRulebook: ...

    @overload
    def _get_rulebook_by_extension(  # noqa: E704
        self, rulebook_path: str, vendor: str, extension: Literal["order"], hw: HardwareView
    ) -> OrderRulebook: ...

    @overload
    def _get_rulebook_by_extension(  # noqa: E704
        self, rulebook_path: str, vendor: str, extension: Literal["deploy"], hw: HardwareView
    ) -> DeployRulebook: ...

    def _get_rulebook_by_extension(
        self, rulebook_path: str, vendor: str, extension: Extension, hw: HardwareView
    ) -> AnyRulebook:
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

    def _split_text_from_inherit_from_param(self, rulebook_text: AnyRulebookText) -> tuple[str | None, str]:
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

    def _parse_inherit_from_param(self, param: str) -> str:
        """Parses the %inherit_from param"""
        parts = param.split("=")
        if len(parts) != 2:
            raise RulebookSyntaxError(r"The %inherit_from param must follow '%inherit_from={path}' format")
        path = parts[1]
        self.check_rulebook_path(path)
        return path

    def check_rulebook_path(self, rulebook_path: str) -> None:
        """Validates the Python path to a rulebook"""
        if not valid_object_path(rulebook_path):
            raise ValueError(f"Invalid rulebook path '{rulebook_path}'. The path must follow the 'module.name' format.")

    def _get_rulebook_text(self, rulebook_path: str, extension: Extension, hw: HardwareView) -> AnyRulebookText:
        """Gets the rulebook text"""
        key = (rulebook_path, extension, hw)
        if key not in self._rulebook_text_cache:
            raw_text = self._get_raw_rulebook_text(rulebook_path, extension)
            escaped_mako_text = self._escape_mako(raw_text)
            rendered_text = mako_render(escaped_mako_text, hw=hw)
            self._rulebook_text_cache[key] = re.sub(r"\n+", "\n", rendered_text.strip("\n"))
        return self._rulebook_text_cache[key]

    def _get_raw_rulebook_text(self, rulebook_path: str, extension: Extension) -> AnyRulebookText:
        """Gets the raw rulebook text"""
        self.check_rulebook_path(rulebook_path)
        module, name = rulebook_path.rsplit(".", 1)
        try:
            return resources.files(module).joinpath(f"{name}.{extension}").read_text(encoding="utf-8")
        except RULEBOOK_READ_EXCEPTIONS as err:
            raise FileNotFoundError(f'Unable to find rulebook "{name}" in "{self.rulebook_module}" module') from err

    @staticmethod
    def _escape_mako(text: str) -> str:
        # Экранирование всего, что начинается на %, например %comment -> %%comment, чтобы он не интерпретировался
        # как mako-оператор
        text = re.sub(r"(?:^|\n)%((?!if\s*|elif\s*|else\s*|endif\s*|for\s*|endfor\s*))", "\n%%\\1", text)
        text = re.sub(r"(?:^|\n)\s*#.*", "", text)
        return text
