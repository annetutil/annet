import functools
import importlib

from annet.annlib.rulebook import common  # pylint: disable=unused-import # noqa: F401,F403
from annet.annlib.rulebook.common import *  # pylint: disable=wildcard-import,unused-wildcard-import # noqa: F401,F403


@functools.lru_cache()
def import_rulebook_function(name):
    module, function_name = name.rsplit(".", 1)
    try:
        module = importlib.import_module(module)
        return getattr(module, function_name)
    except ImportError:
        raise ImportError(f"Could not import {name}")
