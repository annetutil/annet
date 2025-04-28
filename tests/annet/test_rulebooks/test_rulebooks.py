import pytest as pytest
from annet import rulebook

from tests import make_hw_stub
from annet.vendors import registry


@pytest.fixture(params=list(registry))
def vendor(request):
    return request.param


def test_rulebooks(vendor):
    """
    Проходимся по всем возможным вендорам и пытаемся получить рулбуки
    Если в рулбуке будет синтаксическая ошибка в шаблоне (например как в NOCDEV-12134 %else вместо %else:), тест упадет
    """
    hw = make_hw_stub(vendor)
    rulebook.get_rulebook(hw)
