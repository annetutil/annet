from __future__ import annotations

import pkgutil
import re
import types
from typing import (
    FrozenSet,
    Iterable,
    List,
    Optional,
    Set,
    Union,
)

from annet.lib import (
    flatten,
    jinja_render,
    mako_render,
)
from .base import BaseGenerator, _filter_str
from .exceptions import NotSupportedDevice


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

    def supports_device(self, device):
        return bool(self.path(device))

    def run(self, device) -> Union[None, str, Iterable[Union[str, tuple]]]:
        raise NotImplementedError

    def reload(self, device) -> Optional[
        str]:  # pylint: disable=unused-argument
        return

    def get_reload_cmds(self, device) -> str:
        ret = self.reload(device) or ""
        path = self.path(device)
        if path and device.hw.PC and device.hw.soft.startswith(
            ("Cumulus", "SwitchDev", "SONiC"),
        ):
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
            raise Exception("generator %s returns %s" % (
                self.__class__.__name__, type(run_res)))
        for text in run_res:
            if isinstance(text, tuple):
                text = " ".join(map(_filter_str, flatten(text)))
            assert re.search(r"\bNone\b", text) is None, \
                "Found 'None' in yield result: %s" % text
            parts.append(text)
        return "\n".join(parts)
