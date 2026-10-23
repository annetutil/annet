"""Identity-aware diff and patch logic for built-in RouterOS Ethernet interfaces."""

from collections import OrderedDict as odict
from dataclasses import dataclass
from typing import Any

from annet.annlib.rulebook.common import DiffDict, DiffItem, LogicResult, call_diff_logic
from annet.types import Op


@dataclass(frozen=True)
class EthernetSet:
    identity: str
    attrs: dict[str, str]


class EthernetSetParseError(ValueError):
    """Raised when an Ethernet set command cannot be matched safely."""


# RouterOS escape sequences produce raw bytes: ``\f`` is 0xFF rather than a form feed,
# and non-ASCII text is exported as a sequence of ``\XX`` UTF-8 bytes.
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
# ``_`` and ``?`` are decode-only: a space or a question mark inside quotes needs no escape.
_ENCODE_ESCAPES = {value: f"\\{key}" for key, value in _ESCAPES.items() if key not in {"_", "?", "f"}}
# Values that must never be emitted bare, because RouterOS would read them as syntax.
_UNSAFE_BARE = '"\\;[]$?'
_HEX_DIGITS = "0123456789ABCDEF"


def _decode(token: bytearray, row: str) -> str:
    """Decode collected RouterOS bytes as UTF-8, keeping stray bytes round-trippable."""
    try:
        return token.decode("utf-8", "surrogateescape")
    except UnicodeDecodeError as exc:  # pragma: no cover - surrogateescape never raises
        raise EthernetSetParseError(f"Undecodable value in RouterOS Ethernet row: {row!r}") from exc


def _tokenize(row: str) -> list[str]:
    """Split a RouterOS row while decoding quoted escape sequences."""
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
                raise EthernetSetParseError(f"Invalid RouterOS Ethernet row: {row!r}")
            escaped = row[position]
            if escaped in _ESCAPES:
                token += _ESCAPES[escaped]
            elif position + 1 < len(row) and all(char in _HEX_DIGITS for char in row[position : position + 2]):
                token.append(int(row[position : position + 2], 16))
                position += 1
            else:
                raise EthernetSetParseError(f"Invalid escape sequence in RouterOS Ethernet row: {row!r}")
        elif not quoted and character == "\\":
            raise EthernetSetParseError(f"Unexpected escape outside quotes in RouterOS Ethernet row: {row!r}")
        elif not quoted and character in "[]":
            if token:
                tokens.append(_decode(token, row))
                token.clear()
            tokens.append(character)
        elif not quoted and character.isspace():
            if token:
                tokens.append(_decode(token, row))
                token.clear()
        else:
            token += character.encode("utf-8", "surrogateescape")
        position += 1

    if quoted:
        raise EthernetSetParseError(f"Invalid RouterOS Ethernet row: {row!r}")
    if token:
        tokens.append(_decode(token, row))
    return tokens


def _parse_attrs(tokens: list[str], row: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
        else:
            raise EthernetSetParseError(f"Invalid attribute {token!r} in RouterOS Ethernet row: {row!r}")
        if not key or key in attrs:
            raise EthernetSetParseError(f"Duplicate or empty attribute {key!r} in RouterOS Ethernet row: {row!r}")
        attrs[key] = value
    return attrs


def parse_set(row: str, *, allow_positional: bool = False) -> EthernetSet:
    """Parse an Ethernet set row and return its factory-port identity.

    Both the spaced selector form ``[ find default-name=ether1 ]`` and the
    compact generator form ``[find default-name=ether1]`` are accepted.
    RouterOS compact exports may shorten an unchanged factory name to the
    positional form ``set ether1``; callers may allow that form only while
    parsing running configuration.
    """
    tokens = _tokenize(row)

    if len(tokens) < 2 or tokens[0] != "set":
        raise EthernetSetParseError(f"Expected a RouterOS Ethernet set row, got: {row!r}")

    if tokens[1] == "[":
        try:
            close = tokens.index("]", 2)
        except ValueError as exc:
            raise EthernetSetParseError(f"Unclosed selector in RouterOS Ethernet row: {row!r}") from exc
        selector = tokens[2:close]
        if len(selector) != 2 or selector[0] != "find" or not selector[1].startswith("default-name="):
            raise EthernetSetParseError(
                f"Expected a single 'find default-name=...' selector in RouterOS Ethernet row: {row!r}"
            )
        identity = selector[1].split("=", 1)[1]
        attrs_tokens = tokens[close + 1 :]
    elif allow_positional and not tokens[1].isdigit():
        identity = tokens[1]
        attrs_tokens = tokens[2:]
    else:
        raise EthernetSetParseError(f"Expected a 'find default-name=...' selector in RouterOS Ethernet row: {row!r}")

    if not identity:
        raise EthernetSetParseError(f"Empty default-name identity in RouterOS Ethernet row: {row!r}")

    attrs = _parse_attrs(attrs_tokens, row)
    if "default-name" in attrs:
        raise EthernetSetParseError(f"Conflicting default-name identity in RouterOS Ethernet row: {row!r}")
    return EthernetSet(identity=identity, attrs=attrs)


def _index(rows: odict[str, Any], side: str, *, allow_positional: bool) -> dict[str, tuple[str, EthernetSet]]:
    indexed: dict[str, tuple[str, EthernetSet]] = {}
    for row in rows:
        parsed = parse_set(row, allow_positional=allow_positional)
        if parsed.identity in indexed:
            previous = indexed[parsed.identity][0]
            raise EthernetSetParseError(
                f"Duplicate default-name {parsed.identity!r} in {side} RouterOS Ethernet config: {previous!r}, {row!r}"
            )
        indexed[parsed.identity] = (row, parsed)
    return indexed


def _matches_desired(running: EthernetSet, desired: EthernetSet) -> bool:
    """Compare the attributes explicitly owned by the desired row.

    An empty desired value asks RouterOS to clear the property, which is the only
    reset syntax the ``set`` grammar accepts. A cleared property is then omitted
    from the export altogether, so an absent running attribute is already at the
    requested state and must not be reported as drift.
    """
    return all(running.attrs.get(key, "") == value for key, value in desired.attrs.items())


def diff(
    old: odict[str, Any], new: odict[str, Any], diff_pre: odict[str, Any], _pops: tuple[str, ...] = (Op.AFFECTED,)
) -> list[DiffItem]:
    """Pair Ethernet set rows by factory default-name instead of command text."""
    old_by_identity = _index(old, "running", allow_positional=True)
    new_by_identity = _index(new, "desired", allow_positional=False)
    old_positions = {identity: position for position, identity in enumerate(old_by_identity)}
    items: list[tuple[int, DiffItem]] = []

    for identity, (new_row, desired) in new_by_identity.items():
        if identity in old_by_identity:
            old_row, running = old_by_identity[identity]
            changed = not _matches_desired(running, desired)
            op = Op.MOVED if changed else _pops[-1]
            children = call_diff_logic(
                diff_pre[new_row]["subtree"], old.get(old_row, odict()), new[new_row], _pops + (op,)
            )
            position = old_positions[identity]
            row = new_row if changed else old_row
        else:
            op = Op.ADDED
            children = call_diff_logic(diff_pre[new_row]["subtree"], odict(), new[new_row], _pops + (op,))
            position = len(old_by_identity) + len(items)
            row = new_row

        items.append(
            (
                position,
                DiffItem(op=op, row=row, children=children, diff_pre=diff_pre[new_row]["match"]),
            )
        )

    # A built-in interface that is absent from desired state is unmanaged, not removed.
    for identity, (old_row, _) in old_by_identity.items():
        if identity in new_by_identity:
            continue
        children = call_diff_logic(diff_pre[old_row]["subtree"], old[old_row], odict(), _pops + (Op.AFFECTED,))
        items.append(
            (
                old_positions[identity],
                DiffItem(op=Op.AFFECTED, row=old_row, children=children, diff_pre=diff_pre[old_row]["match"]),
            )
        )

    items.sort(key=lambda pair: pair[0])
    return [item for _, item in items]


def _quote(value: str) -> str:
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
            # Control bytes and non-ASCII text are emitted the way RouterOS exports them.
            escaped.append(f"\\{byte:02X}")
    return '"' + "".join(escaped) + '"'


def _render(row: str) -> str:
    parsed = parse_set(row)
    parts = ["set", "[", "find", f"default-name={_quote(parsed.identity)}", "]"]
    for key, value in parsed.attrs.items():
        parts.append(f"{key}={_quote(value)}")
    return " ".join(parts)


def change(rule: dict[str, Any], key: tuple[str, ...], diff: DiffDict, **_: Any) -> LogicResult:
    """Render changed desired rows as targeted in-place set commands."""
    del rule, key
    for item in diff[Op.ADDED] + diff[Op.MOVED]:
        yield True, _render(item["row"]), item["children"]
    for item in diff[Op.AFFECTED]:
        yield True, item["row"], item["children"]
