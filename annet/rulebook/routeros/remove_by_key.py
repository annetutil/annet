from collections.abc import Iterator
from ipaddress import ip_address
from typing import Any

from contextlog import get_logger

from annet.annlib.types import Op
from annet.vendors.library.routeros import RouterOSParseError, parse_attrs, quote, tokenize


def _attrs(row: str) -> dict[str, str]:
    parts = tokenize(row)
    if not parts:
        raise RouterOSParseError(f"Empty RouterOS command: {row!r}")
    start = 1
    if parts[0] == "set" and len(parts) > 1:
        if parts[1] == "[":
            try:
                close = parts.index("]", 2)
            except ValueError as exc:
                raise RouterOSParseError(f"Unclosed selector in RouterOS row: {row!r}") from exc
            # find inside a selector carries identity attributes; read them like shlex did
            start = 2
            parts = parts[:close] + parts[close + 1 :]
        elif "=" not in parts[1]:
            start = 2
    # Keep the legacy permissive extraction of non-attribute words and duplicate keys.
    attrs = [part for part in parts[start:] if "=" in part]
    return {key.lower(): value for key, value in parse_attrs(attrs, row, strict=False).items()}


def change(
    key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], **kwargs: Any
) -> Iterator[tuple[bool, str, None]]:
    """
    Handle RouterOS operations.

    For Op.ADDED: Use the original command
    For Op.REMOVED: Transform 'add ... name=X ...' to 'remove name="X"'
    Then in tabparser.py will transform to 'remove [ find + cmd + ]'
    """
    for added_cmd in diff[Op.ADDED]:
        original_cmd = added_cmd["row"]
        if "note=" in original_cmd:
            original_cmd += " show-at-cli-login=no"
        yield True, original_cmd, None

    for removed_cmd in diff[Op.REMOVED]:
        original_cmd = removed_cmd["row"]

        try:
            params = _attrs(original_cmd)
        except Exception as e:
            get_logger().error("Command parsing failed: %s", e)
            continue

        # Create remove command using match-case for cleaner logic
        match params:
            case {"name": name}:
                yield True, f"remove name={quote(name)}", None

            case {"peer": peer}:
                if peer.startswith("*"):
                    yield True, "remove about", None
                else:
                    yield True, f"remove peer={quote(peer)}", None

            case {"host": host}:
                yield False, f"remove host={quote(host)}", None

            case {"action": action, "topics": topics}:
                if action.startswith("*"):
                    yield True, "remove invalid", None
                else:
                    yield True, f"remove action={quote(action)} topics={quote(topics)}", None

            case {"address": address, "interface": interface}:
                addr, sep, mask = address.partition("/")
                ip = ip_address(addr)
                if not mask:
                    mask = str(ip.max_prefixlen)
                    address = f"{addr}/{mask}"
                if interface.startswith("*"):
                    yield True, f"remove address={quote(address)}", None
                else:
                    yield True, f"remove address={quote(address)} interface={quote(interface)}", None

            case {"address": address}:
                yield True, f"remove address={quote(address)}", None

            case {"interface": interface, "list": list}:
                if interface.startswith("*"):
                    yield True, f"remove list={quote(list)}", None
                else:
                    yield True, f"remove interface={quote(interface)}", None

            case {"comment": comment, "dst-address": dst_address, "gateway": gateway}:
                yield (
                    True,
                    f"remove comment={quote(comment)} dst-address={quote(dst_address)} gateway={quote(gateway)}",
                    None,
                )

            case {"comment": comment, "dst-address": dst_address}:
                yield True, f"remove comment={quote(comment)} dst-address={quote(dst_address)}", None

            case {"disabled": disabled, "topics": topics}:
                # remove all disabled topics
                if disabled == "yes":
                    yield True, f"remove disabled={disabled}", None

            case {"topics": topics}:
                topics = topics.replace(",", ".")
                yield True, f"remove topics~{quote(topics)}", None

            case {"disabled": _}:
                # Always turn off www-ssl
                if "www-ssl" in original_cmd:
                    yield True, "set www-ssl disabled=yes", None
