from unittest import mock

import pytest

from annet.hardware import AnnetHardwareProvider, hardware_connector


@pytest.fixture(scope="session", autouse=True)
def ann_connectors():
    hardware_connector.set(AnnetHardwareProvider)


@pytest.fixture
def mock_rulebooks_path(request):
    """
    Fixture for mocking the path field value in default in rulebooks in annet/configs/context.yml

    Usage via parameterization:
        @pytest.mark.parametrize(
            "mock_rulebooks_path",
            ["custom.path.to.rulebook_module"],
            indirect=True,
        )
        def test_example(mock_rulebooks_path):
            ...

    The "custom.path.to.rulebook" parameter will be substituted into the path field value in default in rulebooks in
    annet/configs/context.yml:
        rulebooks:
          default:
            path: custom.path.to.rulebook
    when using the annet.lib.get_context function in annet.rulebook.__init__.RulebookProvider
    """
    from copy import deepcopy

    from annet.lib import get_context

    original_context = get_context()

    custom_context = deepcopy(original_context)
    custom_context["rulebooks"]["path"] = request.param

    with mock.patch("annet.rulebook.get_context", return_value=custom_context):
        yield request.param
