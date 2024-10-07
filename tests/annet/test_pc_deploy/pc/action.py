from typing import Optional

from annet.api import HardwareView
from annet.deploy import CommandList, Command


def apply(hw: HardwareView, do_commit: bool, do_finalize: bool, path: Optional[str] = None, **_):
    before_cmd = getattr(hw, "__before", "")
    after_cmd = getattr(hw, "__after", "")
    before, after = CommandList(cmss=[Command(before_cmd)]), CommandList(cmss=[Command(after_cmd)])

    return before, after
