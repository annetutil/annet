import pytest
from unittest import mock

from annet.hardware import AnnetHardwareProvider, hardware_connector


@pytest.fixture(scope="session", autouse=True)
def ann_connectors():
    hardware_connector.set(AnnetHardwareProvider)


@pytest.fixture
def mock_rulebook_module(request):
    """
    Fixture для мокания rulebook_module в annet/configs/context.yml с кастомным значением.
    
    Использование через параметризацию:
    @pytest.mark.parametrize(
        "mock_rulebook_module",
        ["custom.rulebook.texts"],
        indirect=True,
    )
    def test_example(mock_rulebook_module):
        ...
    Значение ["custom.rulebook.texts"] будет подставлен в "rulebook_module" в context файл при использовании
    функции annet.lib.get_context в annet.rulebook.__init__.DefaultRulebookProvider
    """
    from annet.lib import get_context
    original_context = get_context()
    
    custom_context = original_context.copy()
    
    if isinstance(request.param, str):
        custom_context["rulebook_module"] = [request.param]
    else:
        custom_context["rulebook_module"] = request.param
    
    with mock.patch("annet.rulebook.get_context", return_value=custom_context):
        yield request.param
