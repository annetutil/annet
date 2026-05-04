from annet.rulebook import DefaultRulebookProvider
from annet.rulebook.patching import compile_patching_text, dump_patch_rulebook
from tests import make_hw_stub
from tests.annet.test_inherit import check_rulebook_equal


def test_text():
    rb_provider = DefaultRulebookProvider()

    hw = make_hw_stub("juniper")
    vendor = hw.vendor

    expected_rb = rb_provider._get_rulebook_by_extension(
        rulebook_path="tests.annet.test_inherit.test_patching.test_parse_text.test_text",
        extension="rul",
        hw=hw,
        vendor=vendor,
    )
    rulebook_text = dump_patch_rulebook(expected_rb)
    compiled_rb = compile_patching_text(rulebook_text, vendor)
    check_rulebook_equal(expected_rb, compiled_rb)
