from typing import List

from annet.generators import BaseGenerator
from annet.storage import Storage
from . import policy


def get_generators(store: Storage) -> List[BaseGenerator]:
    return policy.get_generators(store)
