from __future__ import annotations

import functools
from collections.abc import Collection
from typing import Any, Optional

from annet.annlib.netdev.devdb import parse_hw_model

from .dump import DumpableView, _EnumAllAttrs


Seq = tuple[str, ...]


class HardwareLeaf(DumpableView):
    def __new__(cls, *_: Any, **__: Any) -> HardwareLeaf:
        obj = super(HardwareLeaf, cls).__new__(cls)
        obj.__path = ()
        obj.__true_sequences = set()
        obj.__false_sequences = set()
        return obj

    def __init__(self, path: Seq, true_sequences: Collection[Seq], false_sequences: Collection[Seq]) -> None:
        self.__path = path
        self.__true_sequences = true_sequences
        self.__false_sequences = false_sequences

    def __bool__(self) -> bool:
        if len(self.__path) == 0 or self.__path in self.__true_sequences:
            return True
        elif self.__path in self.__false_sequences:
            return False
        raise AttributeError("HW: " + ".".join(self.__path))

    def __getattr__(self, name: str) -> Any:
        path = self.__path + (name,)
        if path in self.__true_sequences or path in self.__false_sequences:
            return HardwareLeaf(path, self.__true_sequences, self.__false_sequences)
        try:
            return self.__dict__[name]
        except KeyError:
            raise AttributeError("HW: " + ".".join(path))

    def __str__(self) -> str:
        for seq in sorted(self.__true_sequences, key=len, reverse=True):
            return ".".join(seq)
        return ""

    def __repr__(self) -> str:
        return str(" | ".join(".".join(x) for x in self.__true_sequences))

    def dump(self, prefix: str = "", value: Any = _EnumAllAttrs, seen: dict[int, str] | None = None) -> list[str]:
        ret = super().dump(prefix, value=value, seen=seen)
        seen_names: set[str] = set()
        for seq in sorted(self.__true_sequences, key=len, reverse=True):
            if any(name in seen_names for name in seq):
                continue
            seen_names.update(seq)
            ret.append("%s.%s = True" % (prefix, ".".join(seq)))
        return ret


class HardwareView(HardwareLeaf):
    def __init__(self, hw_model: Optional[str], sw_version: Optional[str] = None) -> None:
        true_sequences, false_sequences = parse_hw_model(hw_model or "")
        super().__init__((), true_sequences, false_sequences)
        self.model = hw_model or ""
        self._soft = sw_version or ""

    @property
    def vendor(self) -> Optional[str]:
        from annet.hardware import hardware_connector

        return hardware_connector.get().hw_to_vendor(self)

    @property
    def soft(self) -> str:
        return self._soft

    @soft.setter
    def soft(self, value: str) -> None:
        self._soft = value

    def match(self, expr: str) -> bool:
        dev_path = expr.split(".")
        if dev_path and dev_path[0] == "hw":
            dev_path = dev_path[1:]
        return bool(functools.reduce(getattr, dev_path, self))

    def __hash__(self) -> int:
        return hash(self.model)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HardwareView):
            return NotImplemented
        return self.model == other.model


def lag_name(hw: HardwareView, nlagg: int) -> str:
    if hw.Huawei:
        return f"Eth-Trunk{nlagg}"
    if hw.Cisco:
        return f"port-channel{nlagg}"
    if hw.Nexus:
        return f"port-channel{nlagg}"
    if hw.Arista:
        return f"Port-Channel{nlagg}"
    if hw.Juniper:
        return f"ae{nlagg}"
    if hw.Nokia:
        return f"lag-{nlagg}"
    if hw.PC.Whitebox:
        return f"bond{nlagg}"
    if hw.PC:
        return f"lagg{nlagg}"
    if hw.Nokia:
        return f"lagg-{nlagg}"
    if hw.H3C:
        return f"Bridge-Aggregation{nlagg}"
    raise NotImplementedError(hw)
