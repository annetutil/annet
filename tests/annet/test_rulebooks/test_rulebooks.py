import pytest as pytest

from annet import rulebook
from annet.vendors import registry
from tests import make_hw_stub


@pytest.fixture(params=list(registry))
def vendor(request):
    return request.param


def test_rulebooks(vendor):
    """
    Walk through every possible vendor and try to load its rulebooks
    If a rulebook has a syntax error in its template (for example %else instead of %else: as in NOCDEV-12134), the test fails
    """
    hw = make_hw_stub(vendor)
    rulebook.get_rulebook(hw)
