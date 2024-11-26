from annet.generators import BaseGenerator
from annet.storage import Storage
from tests.annet.test_mesh.test_executor import storage
from . import generator


def get_generators(storage: Storage) -> list[BaseGenerator]:
    return generator.get_generators(storage)
