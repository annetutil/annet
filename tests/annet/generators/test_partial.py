from annet.generators.partial import PartialGenerator
from annet.types import BLOCK_HOLDER


def test_empty_block():
    class TestGenerator(PartialGenerator):
        def acl(self, device):
            return r"""
                evpn
                    mac-duplication
                """

        def run(self, device):
            with self.block("evpn"):
                with self.block("mac-duplication"):
                    pass
            yield from []

    gen = TestGenerator(None)
    assert gen(None) == f"evpn\n  {BLOCK_HOLDER}\n  mac-duplication\n    {BLOCK_HOLDER}\n"
