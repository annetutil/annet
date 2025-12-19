import re
from typing import Any, Dict, Iterator, Optional, Set, Tuple

from annet.annlib.lib import cisco_collapse_vlandb as collapse_vlandb
from annet.annlib.lib import cisco_expand_vlandb as expand_vlandb
from annet.annlib.types import Op


# Constants
NEXUS_SWITCHPORT_VLAN_CHUNK: int = 64
NEXUS_DEFAULT_RANGE: range = range(1, 4095)  # 4094 inclusive


def swtrunk(
    rule: Dict[str, Any], key: Tuple, diff: Dict[str, Any], **_
) -> Iterator[Tuple[bool, str, Optional[list]]]:
    """
    Patch logic for Cisco Nexus `switchport trunk allowed vlan` command.
    Processes VLAN configuration changes and yields commands to apply.
    """
    yield from _process_vlandb(rule, key, diff, NEXUS_SWITCHPORT_VLAN_CHUNK)


def _process_vlandb(
    rule: Dict[str, Any], key: Tuple, diff: Dict[str, Any], chunk_size: int
) -> Iterator[Tuple[bool, str, Optional[list]]]:
    """
    Core logic for processing VLAN database changes.

    Args:
        rule: Configuration rule dictionary
        key: Rule identifier tuple
        diff: Dictionary containing ADDED, REMOVED, and AFFECTED operations
        chunk_size: Maximum number of VLAN ranges per command

    Yields:
        Tuples of (should_add: bool, command: str, children: Optional[list])
    """
    # Early exit if no changes
    if not diff[Op.ADDED] and not diff[Op.REMOVED]:
        return

    # Process affected blocks with modified content
    for affected in diff[Op.AFFECTED]:
        yield (True, affected["row"], affected["children"])

    # Parse added and removed VLAN configurations
    pref_added, vlans_new, new_blocks = _parse_vlancfg_actions(diff[Op.ADDED])
    pref_removed, vlans_old, old_blocks = _parse_vlancfg_actions(diff[Op.REMOVED])

    # Handle case where no existing configuration exists
    if not diff[Op.REMOVED]:
        vlans_old = set(NEXUS_DEFAULT_RANGE)

    # Use removed prefix if added prefix is not available
    if not pref_added:
        pref_added = pref_removed

    # Handle "none" configuration special case
    if len(diff[Op.ADDED]) == 1 and not vlans_new:
        yield (True, f"{pref_added} none", None)
        return

    # Process blocks where VLAN remains but content changed
    removed_blocks_keys = set(old_blocks.keys()) - set(new_blocks.keys())
    for vlan_id in removed_blocks_keys & vlans_new:
        yield (True, f"{pref_added} {vlan_id}", old_blocks[vlan_id])

    # Calculate VLANs to add and remove
    vlans_to_remove = vlans_old - vlans_new
    vlans_to_add = vlans_new - vlans_old

    # Generate remove commands in chunks
    if vlans_to_remove:
        collapsed_remove = collapse_vlandb(vlans_to_remove)
        for chunk in _chunked(collapsed_remove, chunk_size):
            yield (False, f"{pref_added} remove {','.join(chunk)}", None)

    # Generate add commands in chunks
    if vlans_to_add:
        collapsed_add = collapse_vlandb(vlans_to_add)
        for chunk in _chunked(collapsed_add, chunk_size):
            yield (True, f"{pref_added} add {','.join(chunk)}", None)

    # Process new VLAN blocks
    for vlan_id, block in new_blocks.items():
        yield (True, f"{pref_added} {vlan_id}", block)


def _chunked(items: list, chunk_size: int) -> Iterator[list[str]]:
    """
    Split a list into chunks of specified size.

    Args:
        items: List to split
        chunk_size: Maximum size of each chunk

    Yields:
        Chunks of the original list
    """
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def _parse_vlancfg_actions(
    actions: list[Dict[str, Any]],
) -> Tuple[Optional[str], Set[int], Dict[str, Any]]:
    """
    Parse VLAN configuration actions to extract prefix, VLAN IDs, and blocks.

    Args:
        actions: List of action dictionaries with 'row' and 'children' keys

    Returns:
        Tuple of (prefix, vlan_ids, blocks)
    """
    prefix: Optional[str] = None
    vlan_ids: Set[int] = set()
    blocks: Dict[str, Any] = {}

    for action in actions:
        current_prefix, vlan_set = _parse_vlancfg(action["row"])

        # Use the first encountered prefix
        if prefix is None:
            prefix = current_prefix

        # Handle VLAN blocks with children
        if action["children"]:
            if len(vlan_set) != 1:
                raise ValueError(
                    f"VLAN block must contain exactly one VLAN ID: {action['row']}"
                )
            vlan_id = next(iter(vlan_set))
            blocks[str(vlan_id)] = action["children"]

        vlan_ids.update(vlan_set)

    return prefix, vlan_ids, blocks


def _parse_vlancfg(row: str) -> Tuple[str, Set[int]]:
    """
    Parse Cisco VLAN configuration string into prefix and VLAN IDs.

    Args:
        row: Configuration string (e.g., "switchport trunk allowed vlan 1-10,20")

    Returns:
        Tuple of (command_prefix, set_of_vlan_ids)

    Raises:
        ValueError: If the row cannot be parsed
    """
    # Normalize spaces around commas
    normalized_row = re.sub(r",\s+", ",", row)
    words = normalized_row.split()

    # Handle "none" configuration
    if words[-1] == "none":
        prefix = " ".join(words[:-1])
        return prefix, set()

    # Validate VLAN configuration format
    if not re.match(r"[\d,-]+$", words[-1]):
        raise ValueError(f"Unable to parse VLAN configuration row: {row}")

    # Extract prefix and VLAN configuration
    prefix_words = words[:-2] if words[-2] == "add" else words[:-1]
    prefix = " ".join(prefix_words)
    vlan_config = words[-1]

    # Expand VLAN ranges to individual IDs
    vlan_ids = expand_vlandb(vlan_config)

    return prefix, vlan_ids
