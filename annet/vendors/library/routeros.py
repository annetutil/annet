from typing import Any

from annet.annlib.command import Command, CommandList
from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry
from annet.vendors.tabparser import RosFormatter


class RouterOSParseError(ValueError):
    """Raised when a RouterOS command contains malformed tokens or attributes."""


# RouterOS escapes produce bytes: \f is 0xFF, and non-ASCII values use UTF-8 \XX escapes.
_ESCAPES = {
    '"': b'"',
    "\\": b"\\",
    "n": b"\n",
    "r": b"\r",
    "t": b"\t",
    "$": b"$",
    "?": b"?",
    "_": b" ",
    "a": b"\a",
    "b": b"\b",
    "f": b"\xff",
    "v": b"\v",
}
_ENCODE_ESCAPES = {value: f"\\{key}" for key, value in _ESCAPES.items() if key not in {"_", "?", "f"}}
_UNSAFE_BARE = '"\\;[]$?'
_HEX_DIGITS = "0123456789ABCDEF"


def _decode(token: bytearray) -> str:
    """Decode RouterOS bytes while preserving stray bytes for round trips."""
    return token.decode("utf-8", "surrogateescape")


def tokenize(row: str) -> list[str]:
    """Split a RouterOS row and decode escapes within quoted values."""
    tokens: list[str] = []
    token = bytearray()
    quoted = False
    position = 0

    while position < len(row):
        character = row[position]
        if character == '"':
            quoted = not quoted
        elif quoted and character == "\\":
            position += 1
            if position == len(row):
                raise RouterOSParseError(f"Invalid RouterOS row: {row!r}")
            escaped = row[position]
            if escaped in _ESCAPES:
                token += _ESCAPES[escaped]
            elif position + 1 < len(row) and all(char in _HEX_DIGITS for char in row[position : position + 2]):
                token.append(int(row[position : position + 2], 16))
                position += 1
            else:
                raise RouterOSParseError(f"Invalid escape sequence in RouterOS row: {row!r}")
        elif not quoted and character == "\\":
            raise RouterOSParseError(f"Unexpected escape outside quotes in RouterOS row: {row!r}")
        elif not quoted and character in "[]":
            if token:
                tokens.append(_decode(token))
                token.clear()
            tokens.append(character)
        elif not quoted and character.isspace():
            if token:
                tokens.append(_decode(token))
                token.clear()
        else:
            token += character.encode("utf-8", "surrogateescape")
        position += 1

    if quoted:
        raise RouterOSParseError(f"Invalid RouterOS row: {row!r}")
    if token:
        tokens.append(_decode(token))
    return tokens


def parse_attrs(tokens: list[str], row: str, *, strict: bool = True) -> dict[str, str]:
    """Parse key=value tokens; optionally preserve legacy last-value-wins behavior."""
    attrs: dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            raise RouterOSParseError(f"Invalid attribute {token!r} in RouterOS row: {row!r}")
        key, value = token.split("=", 1)
        if strict and (not key or key in attrs):
            raise RouterOSParseError(f"Duplicate or empty attribute {key!r} in RouterOS row: {row!r}")
        attrs[key] = value
    return attrs


def quote(value: str) -> str:
    """Render one value without exposing RouterOS command metacharacters."""
    if value and all("!" <= character <= "~" and character not in _UNSAFE_BARE for character in value):
        return value
    escaped = []
    for byte in value.encode("utf-8", "surrogateescape"):
        single = bytes((byte,))
        if single in _ENCODE_ESCAPES:
            escaped.append(_ENCODE_ESCAPES[single])
        elif 0x20 <= byte <= 0x7E:
            escaped.append(chr(byte))
        else:
            escaped.append(f"\\{byte:02X}")
    return '"' + "".join(escaped) + '"'


@registry.register
class RouterOSVendor(AbstractVendor):
    NAME = "routeros"

    def apply(
        self, hw: HardwareView, do_commit: bool, do_finalize: bool, path: str | None
    ) -> tuple[CommandList, CommandList]:
        before, after = CommandList(), CommandList()

        # FIXME: could not get rid of \x1b[c after enabling safe mode yet
        # if len(cmds) > 99:
        #     raise Exception("RouterOS does not support more 100 actions in safe mode")
        # before.add_cmd(RosDevice.SAFE_MODE)
        pass
        # after.add_cmd(RosDevice.SAFE_MODE)

        return before, after

    def match(self) -> list[str]:
        return ["RouterOS"]

    @property
    def reverse(self) -> str:
        return "remove"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("RouterOS")

    def make_formatter(self, **kwargs: Any) -> RosFormatter:
        return RosFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return ""
