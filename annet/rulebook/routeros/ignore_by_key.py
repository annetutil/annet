from collections import OrderedDict
from typing import Any

from contextlog import get_logger

from annet.annlib.rulebook.common import DiffItem, default_diff
from annet.annlib.types import Op
from annet.vendors.library.routeros import parse_attrs, quote, tokenize


def _normalize_command(
    command_line: str, ignore_keys: list[str] | None = None, match_word: str = "comment=DHCP"
) -> str:
    """Remove specified keys from commands when match_word is found for comparison.

    Args:
        command_line: RouterOS command line to normalize
        ignore_keys: List of parameter keys to ignore (default: ['local-address', 'gateway', 'src-address', 'disabled'])
        match_word: Word to match in command line to trigger normalization (default: 'comment=DHCP')

    Returns:
        Normalized command line with specified keys removed

    Note:
        All specified keys are ignored when match_word is found in the command
    """
    if match_word not in command_line:
        return command_line

    if ignore_keys is None:
        ignore_keys = ["local-address", "src-address", "gateway", "disabled"]

    # Simplified logic - ignore all specified keys when DHCP comment is present

    result_command = "add"
    try:
        parts = tokenize(command_line)

        start = 1
        if parts and parts[0] == "set" and len(parts) > 1:
            if parts[1] == "[":
                start = parts.index("]", 2) + 1
            elif "=" not in parts[1]:
                start = 2
        selector = parts[1:start]
        if selector:
            result_command += " " + " ".join(selector)
        for part in parts[start:]:
            if "=" in part:
                key_part, value = next(iter(parse_attrs([part], command_line).items()))
                if key_part in ignore_keys:
                    continue
                result_command += f" {key_part}={quote(value)}"
            else:
                result_command += f" {quote(part)}"

        return result_command.strip()

    except Exception as e:
        get_logger().error("Failed to normalize IPSec command: %s", e)
        return command_line


def dhcpclient_change(
    old: OrderedDict[str, Any],
    new: OrderedDict[str, Any],
    diff_pre: OrderedDict[str, Any],
    _pops: tuple[str, ...] = (Op.AFFECTED,),
) -> list[DiffItem]:
    """
    Custom diff logic for RouterOS that ignores specified parameters
    when comment contains "DHCP".

    By default ignores: local-address, gateway, src-address, disabled
    """
    # Normalize both old and new configurations
    normalized_old = OrderedDict(((_normalize_command(k), v) for k, v in old.items()))
    normalized_new = OrderedDict(((_normalize_command(k), v) for k, v in new.items()))

    # Also normalize diff_pre keys to match
    normalized_diff_pre = OrderedDict()
    for k, v in diff_pre.items():
        normalized_key = _normalize_command(k)
        normalized_diff_pre[normalized_key] = v

    return default_diff(normalized_old, normalized_new, normalized_diff_pre, _pops)
