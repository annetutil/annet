import abc
import difflib
from pathlib import Path
from typing import List, Optional, Protocol

from annet import patching, rulebook
from annet.annlib.diff import gen_pre_as_diff
from annet.annlib.netdev.views.hardware import HardwareView
from annet.connectors import CachedConnector
from annet.vendors import registry_connector, tabparser


class FileDiffer(Protocol):
    @abc.abstractmethod
    def diff_file(self, hw: HardwareView, path: str | Path, old: str | None, new: str | None) -> list[str]:
        raise NotImplementedError


class UnifiedFileDiffer(FileDiffer):
    def __init__(self) -> None:
        self.context: int = 3

    def diff_file(self, hw: HardwareView, path: str | Path, old: str | None, new: str | None) -> list[str]:
        """Calculate the differences for config files.

        Args:
            hw: device hardware info
            path: path to file on a device
            old (Optional[str]): The old file content.
            new (Optional[str]): The new file content.

        Returns:
            List[str]: List of difference lines.
        """
        return self._diff_text_file(old, new)

    def _diff_text_file(self, old: str | None, new: str | None) -> list[str]:
        """Calculate the differences for plaintext files."""
        context = self.context
        old_lines = old.splitlines() if old else []
        new_lines = new.splitlines() if new else []
        context = max(len(old_lines), len(new_lines)) if context is None else context
        return list(difflib.unified_diff(old_lines, new_lines, n=context, lineterm=""))


class FrrFileDiffer(UnifiedFileDiffer):
    def diff_file(self, hw: HardwareView, path: str | Path, old: str | None, new: str | None) -> list[str]:
        if (hw.PC.Mellanox or hw.PC.NVIDIA) and (path == "/etc/frr/frr.conf"):
            return self._diff_frr_conf(hw, old, new)
        return super().diff_file(hw, path, old, new)

    def _diff_frr_conf(self, hw: HardwareView, old_text: str | None, new_text: str | None) -> list[str]:
        """Calculate the differences for frr.conf files."""
        indent = "  "
        rb = rulebook.rulebook_provider_connector.get()
        rulebook_data = rb.get_rulebook(hw)
        formatter = registry_connector.get().match(hw).make_formatter(indent=indent)

        old_tree = tabparser.parse_to_tree(old_text or "", splitter=formatter.split)
        new_tree = tabparser.parse_to_tree(new_text or "", splitter=formatter.split)

        diff_tree = patching.make_diff(old_tree, new_tree, rulebook_data, [])
        pre_diff = patching.make_pre(diff_tree)
        diff_iterator = gen_pre_as_diff(pre_diff, show_rules=False, indent=indent, no_color=True)

        return [line.rstrip() for line in diff_iterator if "frr version" not in line]


class _FileDifferConnector(CachedConnector[FileDiffer]):
    name = "Device file diff processor"
    ep_name = "file_differ"


file_differ_connector = _FileDifferConnector()
