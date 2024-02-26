import pytest as pytest
from annet import rulebook
from annet.annlib.rbparser.platform import VENDOR_REVERSES

from tests import make_hw_stub


@pytest.fixture(params=VENDOR_REVERSES.keys())
def vendor(request):
    return request.param


def test_rulebooks(vendor):
    """
    Проходимся по всем возможным вендорам и пытаемся получить рулбуки
    Если в рулбуке будет синтаксическая ошибка в шаблоне (например как в NOCDEV-12134 %else вместо %else:), тест упадет
    """
    hw = make_hw_stub(vendor)
    rulebook.get_rulebook(hw)
