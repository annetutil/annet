from typing import List

from annet.generators import BaseGenerator
from annet.storage import Storage
from . import policy_generator


def get_generators(store: Storage) -> List[BaseGenerator]:
    return policy_generator.get_generators(store)
