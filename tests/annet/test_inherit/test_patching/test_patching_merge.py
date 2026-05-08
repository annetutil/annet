import pytest

from annet.rulebook import DefaultRulebookProvider
from tests import make_hw_stub
from tests.annet.test_inherit import check_patch_rulebook_equal, get_tests_data


@pytest.mark.parametrize(
    "mock_rulebooks",
    get_tests_data("annet/test_inherit/test_patching/test_merge"),
    ids=lambda val: f"file={val[0]}, case={val[1]}",
    indirect=True,
)
def test_merge(mock_rulebooks):
    rb_provider = DefaultRulebookProvider()
    hw = make_hw_stub("juniper")
    vendor = hw.vendor
    inherited_rb = rb_provider._get_rulebook_by_extension(rulebook_path="child", extension="rul", hw=hw, vendor=vendor)
    expected_rb = rb_provider._get_rulebook_by_extension(
        rulebook_path="expected", extension="rul", hw=hw, vendor=vendor
    )
    check_patch_rulebook_equal(inherited_rb, expected_rb)
