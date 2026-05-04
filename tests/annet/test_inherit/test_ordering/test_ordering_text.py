from annet.annlib.rbparser.ordering import compile_ordering_text, dump_order_rulebook
from annet.rulebook import DefaultRulebookProvider
from tests import make_hw_stub


def test_text():
    rb_provider = DefaultRulebookProvider()

    hw = make_hw_stub("juniper")
    vendor = hw.vendor

    expected_rb = rb_provider._get_rulebook_by_extension(
        rulebook_path="tests.annet.test_inherit.test_ordering.test_parse_text.test_text",
        extension="order",
        hw=hw,
        vendor=vendor,
    )
    rulebook_text = dump_order_rulebook(expected_rb)
    compiled_rb = compile_ordering_text(rulebook_text, vendor)
    assert expected_rb == compiled_rb
