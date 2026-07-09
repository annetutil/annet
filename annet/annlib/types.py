import enum
from typing import Final, Literal, get_args


OpType = Literal["added", "removed", "affected", "moved", "unchanged"]


class Op:
    ADDED: Final = "added"
    REMOVED: Final = "removed"
    AFFECTED: Final = "affected"
    MOVED: Final = "moved"
    UNCHANGED: Final = "unchanged"


assert set(get_args(OpType)) == {Op.ADDED, Op.REMOVED, Op.AFFECTED, Op.MOVED, Op.UNCHANGED}


class GeneratorType(enum.Enum):
    PARTIAL = "partial"
    ENTIRE = "entire"
    JSON_FRAGMENT = "json_fragment"

    @staticmethod
    def fromstring(value: str) -> "GeneratorType":
        return GeneratorType(value)

    def tostring(self) -> str:
        return self.value

    def __lt__(self, other: "GeneratorType") -> bool:
        return self.value < other.value

    def __le__(self, other: "GeneratorType") -> bool:
        if self != other:
            return self.value < other.value
        return True
