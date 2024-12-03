from __future__ import annotations

import contextlib
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Union,
)

from annet.storage import Device, Storage
from .base import TreeGenerator, _filter_str
from .exceptions import NotSupportedDevice


class JSONFragment(TreeGenerator):
    """Generates parts of JSON config file."""

    TYPE = "JSON_FRAGMENT"
    TAGS: List[str] = []

    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage
        self._json_config: Dict[str, Any] = {}
        self._config_pointer: List[str] = []

        # if two generators edit same file, commands from generator with greater `reload_prio` will be used
        if not hasattr(self, "reload_prio"):
            self.reload_prio = 100

    def supports_device(self, device: Device):
        return bool(self.path(device))

    def path(self, device: Device) -> Optional[str]:
        raise NotImplementedError("Required PATH for JSON_FRAGMENT generator")

    @classmethod
    def get_aliases(cls) -> Set[str]:
        return {cls.__name__, *cls.TAGS}

    def acl(self, device: Device) -> Union[str, List[str]]:
        """
        Restrict the generator to a specified ACL using JSON Pointer syntax.

        Expected ACL to be a list of strings, but a single string is also allowed.
        """
        raise NotImplementedError("Required ACL for JSON_FRAGMENT generator")

    def acl_safe(self, device: Device) -> Union[str, List[str]]:
        """
        Restrict the generator to a specified safe ACL using JSON Pointer syntax.

        Expected ACL to be a list of strings, but a single string is also allowed.
        """
        raise NotImplementedError("Required ACL for JSON_FRAGMENT generator")

    def run(self, device: Device):
        raise NotImplementedError

    def get_reload_cmds(self, device: Device) -> str:
        ret = self.reload(device) or ""
        return ret

    def reload(self, device) -> Optional[str]:
        raise NotImplementedError

    @contextlib.contextmanager
    def block(self, *tokens, indent=None):  # pylint: disable=unused-argument
        block_str = "".join(map(_filter_str, tokens))
        self._config_pointer.append(block_str)
        try:
            yield
        finally:
            self._config_pointer.pop()

    @contextlib.contextmanager
    def block_piped(self, *tokens, indent=None):  # pylint: disable=unused-argument
        block_str = "|".join(map(_filter_str, tokens))
        self._config_pointer.append(block_str)
        try:
            yield
        finally:
            self._config_pointer.pop()

    def __call__(self, device: Device, annotate: bool = False):
        try:
            for cfg_fragment in self.run(device):
                self._set_or_replace_dict(self._config_pointer, cfg_fragment)
            return self._json_config
        finally:
            self._json_config = {}

    def _set_or_replace_dict(self, pointer, value):
        if not pointer:
            if self._json_config == {}:
                self._json_config = self.process_value(value)
            else:
                self._json_config = [self._json_config, self.process_value(value)]
        else:
            self._set_dict(self._json_config, pointer, value)

    def process_scalar_value(self, value: Any) -> Any:
        return str(value)

    def process_value(self, value: Any) -> Any:
        if isinstance(value, (list, set, frozenset)):
            return [self.process_value(x) for x in value]
        elif isinstance(value, dict):
            for k, v in value.items():
                value[k] = self.process_value(v)
            return value
        return self.process_scalar_value(value)

    def _set_dict(self, cfg, pointer, value):
        # pointer has at least one key
        if len(pointer) == 1:
            if pointer[0] in cfg:
                cfg[pointer[0]] = [cfg[pointer[0]], self.process_value(value)]
            else:
                cfg[pointer[0]] = self.process_value(value)
        else:
            if pointer[0] not in cfg:
                cfg[pointer[0]] = {}
            self._set_dict(cfg[pointer[0]], pointer[1:], self.process_value(value))
