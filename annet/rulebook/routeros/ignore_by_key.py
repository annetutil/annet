import shlex
from collections import OrderedDict

from contextlog import get_logger

from annet.annlib.rulebook.common import default_diff
from annet.annlib.types import Op


def _normalize_command(command_line, ignore_keys=None, match_word="comment=DHCP"):
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
        parts = shlex.split(command_line)

        for part in parts[1:]:  # Skip the 'add' part
            if "=" in part:
                key_part = part.split("=", 1)[0]
                # Skip if key is in ignore_keys
                if key_part in ignore_keys:
                    continue
            result_command += f" {part}"

        return result_command.strip()

    except Exception as e:
        get_logger().error("Failed to normalize IPSec command: %s", e)
        return command_line


def dhcpclient_change(old, new, diff_pre, _pops=(Op.AFFECTED,)):
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
