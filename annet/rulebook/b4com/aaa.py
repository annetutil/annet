import re
from collections import OrderedDict
from typing import Any

from annet.annlib.rulebook.common import DiffItem
from annet.rulebook.common import default_diff


def rsa_key_diff(
    old: OrderedDict[str, Any], new: OrderedDict[str, Any], diff_pre: OrderedDict[str, Any], **kwargs: Any
) -> list[DiffItem]:
    old_hex = _collect_hex_in_order(old)
    new_hex = _collect_hex_in_order(new)
    if old_hex and new_hex and _keys_equal(old_hex, new_hex):
        return []
    else:
        return default_diff(old, new, diff_pre, **kwargs)


def _collect_hex_in_order(block: OrderedDict[str, Any]) -> str:
    parts: list[str] = []

    def _recurse(d: Any) -> None:
        if not isinstance(d, OrderedDict):
            return
        for key, value in d.items():
            if isinstance(key, str) and re.fullmatch(r"[0-9A-Fa-f ]+", key.strip()):
                parts.append(key.strip())
            if isinstance(value, OrderedDict):
                _recurse(value)

    _recurse(block)
    return re.sub(r"\s+", "", "".join(parts)).upper()


def _keys_equal(hex1: str, hex2: str) -> bool:
    try:
        mod1, exp1 = _extract_mod_exp(hex1)
        mod2, exp2 = _extract_mod_exp(hex2)
        return mod1 == mod2 and exp1 == exp2
    except Exception:
        return False


def _extract_mod_exp(hex_str: str) -> tuple[str, str]:
    data = bytes.fromhex(hex_str)
    integers = _collect_all_integers(data)
    if len(integers) < 2:
        raise ValueError(f"Not enough integers: {len(integers)}")
    integers.sort(key=lambda x: len(x))
    mod = integers[-1]
    exp = integers[0]
    return mod, exp


def _collect_all_integers(data: bytes) -> list[str]:
    ints = []
    pos = 0
    while pos < len(data):
        if pos >= len(data):
            break
        tag = data[pos]
        pos += 1
        length, pos = _read_der_length(data, pos)
        if tag == 0x02:
            val = data[pos : pos + length]
            if val and val[0] == 0:
                val = val[1:]
            ints.append(val.hex().upper())
            pos += length
        elif tag in (0x30, 0x31):
            ints.extend(_collect_all_integers(data[pos : pos + length]))
            pos += length
        elif tag == 0x03:
            inner_data = data[pos + 1 : pos + length] if length > 1 else b""
            ints.extend(_collect_all_integers(inner_data))
            pos += length
        elif tag == 0x04:
            ints.extend(_collect_all_integers(data[pos : pos + length]))
            pos += length
        elif tag & 0x20:
            ints.extend(_collect_all_integers(data[pos : pos + length]))
            pos += length
        else:
            pos += length
    return ints


def _read_der_length(data: bytes, pos: int) -> tuple[int, int]:
    if pos >= len(data):
        return 0, pos
    if data[pos] & 0x80:
        num_bytes = data[pos] & 0x7F
        pos += 1
        if pos + num_bytes > len(data):
            return 0, pos
        length = int.from_bytes(data[pos : pos + num_bytes], "big")
        pos += num_bytes
        return length, pos
    else:
        length = data[pos]
        pos += 1
        return length, pos
