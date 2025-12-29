"""
Custom diff logic for RouterOS user commands.
"""

import re
from collections import OrderedDict as odict
from annet.types import Op
from annet.annlib.rulebook.common import DiffItem, call_diff_logic


def extract_comment(line: str) -> str:
    """Extract comment value from RouterOS user add command."""
    match = re.search(r'comment=["\']?([^"\'\s]+)["\']?', line)
    return match.group(1) if match else ""


def normalize_user_line(line: str) -> str:
    """Normalize user line by removing password parameter."""
    normalized = re.sub(r'\s+password=["\']?[^"\'\s]+["\']?', '', line)
    return normalized.strip()


def diff(old: odict, new: odict, diff_pre: odict, _pops: tuple[Op, ...] = (Op.AFFECTED,)) -> list[DiffItem]:
    """Custom diff logic for RouterOS user commands."""
    diff_indexed = []

    # Create normalized mappings
    old_normalized = {}
    new_normalized = {}

    for row in old:
        normalized = normalize_user_line(row)
        comment = extract_comment(row)
        old_normalized[normalized] = (row, comment)

    for row in new:
        normalized = normalize_user_line(row)
        comment = extract_comment(row)
        new_normalized[normalized] = (row, comment)

    # Find removed users
    for index, (normalized, (original_row, _)) in enumerate(old_normalized.items()):
        if normalized not in new_normalized:
            children = call_diff_logic(
                diff_pre[original_row]["subtree"],
                old[original_row],
                odict(),
                _pops + (Op.REMOVED,)
            )
            diff_indexed.append((index, DiffItem(
                op=Op.REMOVED,
                row=original_row,
                children=children,
                diff_pre=diff_pre[original_row]["match"],
            )))

    old_indexes = {normalized: index for index, normalized in enumerate(old_normalized)}

    # Process users in new config
    for normalized, (new_row, new_comment) in new_normalized.items():
        if normalized in old_normalized:
            old_row, old_comment = old_normalized[normalized]

            if old_comment == new_comment:
                # Password unchanged - AFFECTED
                children = call_diff_logic(
                    diff_pre[new_row]["subtree"],
                    old.get(old_row, {}),
                    new[new_row],
                    _pops + (Op.AFFECTED,)
                )
                index = old_indexes.get(normalized, len(old_normalized))
                diff_indexed.append((index, DiffItem(
                    op=Op.AFFECTED,
                    row=old_row,
                    children=children,
                    diff_pre=diff_pre[new_row]["match"],
                )))
            else:
                # Password changed - MOVED
                children = call_diff_logic(
                    diff_pre[new_row]["subtree"],
                    old.get(old_row, {}),
                    new[new_row],
                    _pops + (Op.MOVED,)
                )
                index = old_indexes.get(normalized, len(old_normalized))
                diff_indexed.append((index, DiffItem(
                    op=Op.MOVED,
                    row=new_row,
                    children=children,
                    diff_pre=diff_pre[new_row]["match"],
                )))
        else:
            # New user - ADDED
            children = call_diff_logic(
                diff_pre[new_row]["subtree"],
                odict(),
                new[new_row],
                _pops + (Op.ADDED,)
            )
            index = len(old_normalized)
            diff_indexed.append((index, DiffItem(
                op=Op.ADDED,
                row=new_row,
                children=children,
                diff_pre=diff_pre[new_row]["match"],
            )))

    diff_indexed.sort(key=lambda x: x[0])
    return [item for _, item in diff_indexed]
