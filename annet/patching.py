from __future__ import annotations

from typing import cast

from annet import rulebook
from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.patching import (  # pylint: disable=unused-import  # pylint: disable=unused-import
    AclError as AclError,
)
from annet.annlib.patching import (
    AclNotExclusiveError as AclNotExclusiveError,
)
from annet.annlib.patching import Orderer as BaseOrderer
from annet.annlib.patching import (
    PatchTree as PatchTree,
)
from annet.annlib.patching import (
    apply_acl as apply_acl,
)
from annet.annlib.patching import (
    apply_diff_rb as apply_diff_rb,
)
from annet.annlib.patching import (
    make_diff as make_diff,
)
from annet.annlib.patching import (
    make_patch as make_patch,
)
from annet.annlib.patching import (
    make_pre as make_pre,
)
from annet.annlib.patching import (
    strip_unchanged as strip_unchanged,
)


class Orderer(BaseOrderer):
    @classmethod
    def from_hw(cls, hw: HardwareView) -> "Orderer":
        return cls(
            rulebook.get_rulebook(hw)["ordering"],
            cast(str, hw.vendor),
        )
