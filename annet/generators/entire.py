from __future__ import annotations

import pkgutil
import types
from typing import Any, FrozenSet, Iterable, List, Optional, Union

from annet.lib import flatten, mako_render
from annet.storage import Device, Storage

from .base import NONE_SEARCHER, BaseGenerator, _filter_str
from .exceptions import InvalidValueFromGenerator


class Entire(BaseGenerator):
    TYPE = "ENTIRE"
    TAGS: List[str] = []
    REQUIRED_PACKAGES: FrozenSet[str] = frozenset()
    ENSURE_END_NEWLINE = False

    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        # между генераторами для одного и того же path - выбирается тот что больше
        if not hasattr(self, "prio"):
            self.prio = 100
        self.__device: Device | None = None

    def supports_device(self, device: Device) -> bool:
        return bool(self.path(device))

    def run(self, device: Device) -> Union[None, str, Iterable[Union[str, tuple[Any, ...]]]]:
        raise NotImplementedError

    def reload(self, device: Device) -> Optional[str]:  # pylint: disable=unused-argument
        return None

    def get_reload_cmds(self, device: Device) -> str:
        ret = self.reload(device) or ""
        path = self.path(device)
        if (
            path
            and device.hw.PC
            and device.hw.soft.startswith(
                ("Cumulus", "SwitchDev", "SONiC"),
            )
        ):
            parts = []
            if ret:
                parts.append(ret)
            parts.append("/usr/bin/etckeeper commitreload %s" % path)
            return "\n".join(parts)
        return ret

    def path(self, device: Device) -> Optional[str]:
        raise NotImplementedError("Required PATH for ENTIRE generator")

    # pylint: disable=unused-argument
    def is_safe(self, device: Device) -> bool:
        """Output gen results when --acl-safe flag is used"""
        return False

    def read(self, path: str) -> str:
        data = pkgutil.get_data(__name__, path)
        assert data is not None
        return data.decode()

    def mako(self, text: str, **kwargs: Any) -> str:
        return mako_render(text, dedent=True, device=self.__device, **kwargs)

    # =====

    def __call__(self, device: Device) -> str:
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
            if not self.ALLOW_NONE and NONE_SEARCHER.search(text):
                raise InvalidValueFromGenerator("Found 'None' in yield result: %s" % text)
            parts.append(text)

        ret = "\n".join(parts)
        if self.ENSURE_END_NEWLINE and not ret.endswith("\n"):
            ret += "\n"

        return ret
