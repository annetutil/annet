import re

import pytest

from annet.rulebook import DefaultRulebookProvider
from annet.rulebook.exceptions import RulebookSyntaxError
from tests import make_hw_stub
from tests.annet.test_inherit import IncorrectErrorMessage, get_tests_data


@pytest.mark.parametrize(
    "mock_rulebooks",
    get_tests_data("annet/test_inherit/test_ordering/test_invalid_cases"),
    ids=lambda val: f"file={val[0]}, case={val[1]}",
    indirect=True,
)
def test_invelid_cases(mock_rulebooks):
    rb_provider = DefaultRulebookProvider()
    hw = make_hw_stub("juniper")
    vendor = hw.vendor

    if mock_rulebooks["error_message"] is None:
        raise IncorrectErrorMessage(
            f"The error_message field in file {mock_rulebooks['file']} "
            f"in test case {mock_rulebooks['test_case']} is not defined."
        )
    if not isinstance(mock_rulebooks["error_message"], str):
        raise IncorrectErrorMessage(
            f"The error_message field in file {mock_rulebooks['file']} "
            f"in test case {mock_rulebooks['test_case']} is not a string."
        )

    with pytest.raises(RulebookSyntaxError) as exc_info:
        rb_provider._get_rulebook_by_extension(rulebook_path="child", extension="order", hw=hw, vendor=vendor)

    expected_pattern_raw = mock_rulebooks["error_message"]
    expected_pattern_escaped = re.escape(expected_pattern_raw)
    actual_error_message = str(exc_info.value)

    assert re.search(expected_pattern_escaped, actual_error_message) is not None, (
        f'The received error message "{actual_error_message}" does not '
        f'contain the expected error_message "{expected_pattern_raw}".'
    )
