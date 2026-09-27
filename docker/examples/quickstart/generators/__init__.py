from collections.abc import Iterator
from typing import Any

from annet.generators import BaseGenerator, PartialGenerator
from annet.storage import Storage


class Description(PartialGenerator):
    TAGS = ["description"]

    def acl_arista(self, device: Any) -> str:
        return """
        interface
            description
        """

    def run_arista(self, device: Any) -> Iterator[str]:
        for interface in device.interfaces:
            with self.block(f"interface {interface.name}"):
                yield f"description {interface.description}"


def get_generators(store: Storage) -> list[BaseGenerator]:
    return [Description(store)]
