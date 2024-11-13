from typing import List

from annet.generators import BaseGenerator
from annet.storage import Storage

from . import lldp


def get_generators(store: Storage) -> List[BaseGenerator]:
    return lldp.get_generators(store)
