from unittest import mock

import pytest

from tests.annet.test_inherit import TestRulebookNotFoundError, mock_get_raw_rulebook_text


@pytest.fixture
def mock_rulebooks(request):
    """Fixture for mock rulebooks"""
    file, test_case, rulebooks = request.param
    mock_obj = mock_get_raw_rulebook_text(rulebooks)

    with mock.patch("annet.rulebook.DefaultRulebookProvider._get_raw_rulebook_text", side_effect=mock_obj):
        try:
            yield {"file": file, "test_case": test_case}
        except TestRulebookNotFoundError as err:
            raise TestRulebookNotFoundError(f"Rulebook not found in file '{file}', test case '{test_case}'.") from err
