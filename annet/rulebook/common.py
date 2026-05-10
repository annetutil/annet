import functools
import importlib
from typing import Literal

from valkit.common import valid_bool

from annet.annlib.rulebook import common  # pylint: disable=unused-import # noqa: F401,F403
from annet.annlib.rulebook.common import *  # pylint: disable=wildcard-import,unused-wildcard-import # noqa: F401,F403
from annet.rulebook.exceptions import RulebookSyntaxError
from annet.rulebook.types import OrderRuleAttrs, PatchRuleAttrs, RawParams, Row


CONTEXT: Literal["context"] = "context"


@functools.lru_cache()
def import_rulebook_function(name):
    module, function_name = name.rsplit(".", 1)
    try:
        module = importlib.import_module(module)
        return getattr(module, function_name)
    except ImportError:
        raise ImportError(f"Could not import {name}")


def get_merged_params(parent_params: RawParams, child_params: RawParams) -> RawParams:
    """Merges parent_params and child_params"""
    params = parent_params.copy()
    params.update(child_params)
    return params


def validate_context_compatibility(
    parent_attrs: PatchRuleAttrs | OrderRuleAttrs, child_attrs: PatchRuleAttrs | OrderRuleAttrs, row: Row
) -> None:
    """Checks compatibility of rule contexts"""
    if parent_attrs[CONTEXT] != child_attrs[CONTEXT]:
        raise RulebookSyntaxError(
            f"Merge error for rule '{row}'. Rule contexts must match in parent and child rulebooks."
        )


def raw_param_to_bool(raw_param_value: str | None) -> bool:
    """
    Converts the raw param value to boolean
    Returns True if the param is present and has a valid boolean value of True
    """
    if raw_param_value is None:
        return False
    return valid_bool(raw_param_value if raw_param_value != "" else "1")
