import shlex
from ipaddress import ip_address

from contextlog import get_logger

from annet.annlib.types import Op


def change(key, diff, **kwargs):
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
            parts = shlex.split(original_cmd)
        except Exception as e:
            get_logger().error("Command parsing failed: %s", e)
            continue

        # Parse parameters into dictionary
        params = {}
        for part in parts[1:]:  # Skip the 'add' part
            if "=" in part:
                key_part, value = part.split("=", 1)
                params[key_part.lower()] = value

        # Create remove command using match-case for cleaner logic
        match params:
            case {"name": name}:
                yield True, f'remove name="{name}"', None

            case {"peer": peer}:
                if peer.startswith("*"):
                    yield True, "remove about", None
                else:
                    yield True, f'remove peer="{peer}"', None

            case {"host": host}:
                yield False, f'remove host="{host}"', None

            case {"action": action, "topics": topics}:
                if action.startswith("*"):
                    yield True, "remove invalid", None
                else:
                    yield True, f'remove action="{action}" topics="{topics}"', None

            case {"address": address, "interface": interface}:
                addr, sep, mask = address.partition("/")
                ip = ip_address(addr)
                if not mask:
                    mask = ip.max_prefixlen
                    address = f"{addr}/{mask}"
                if interface.startswith("*"):
                    yield True, f'remove address="{address}"', None
                else:
                    yield True, f'remove address="{address}" interface="{interface}"', None

            case {"address": address}:
                yield True, f'remove address="{address}"', None

            case {"interface": interface, "list": list}:
                if interface.startswith("*"):
                    yield True, f'remove list="{list}"', None
                else:
                    yield True, f'remove interface="{interface}"', None

            case {"comment": comment, "dst-address": dst_address, "gateway": gateway}:
                yield True, f'remove comment="{comment}" dst-address="{dst_address}" gateway="{gateway}"', None

            case {"comment": comment, "dst-address": dst_address}:
                yield True, f'remove comment="{comment}" dst-address="{dst_address}"', None

            case {"disabled": disabled, "topics": topics}:
                # remove all disabled topics
                if disabled == "yes":
                    yield True, f"remove disabled={disabled}", None

            case {"topics": topics}:
                topics = topics.replace(",", ".")
                yield True, f'remove topics~"{topics}"', None

            case {"disabled": _}:
                # Always turn off www-ssl
                if "www-ssl" in original_cmd:
                    yield True, "set www-ssl disabled=yes", None
