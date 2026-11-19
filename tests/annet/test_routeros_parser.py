import pytest

from annet.rulebook.routeros.ignore_by_key import _normalize_command
from annet.rulebook.routeros.remove_by_key import change
from annet.types import Op
from annet.vendors.library.routeros import RouterOSParseError, parse_attrs, quote, tokenize


def test_parse_routeros_escape_sequences():
    row = (
        r'add comment="one\ntwo\rthree\tfour\_five" '
        r'controls="\a\b\v" symbols="\"\\\$\?" hex="\48\45\4C\4C\4F"'
    )
    assert parse_attrs(tokenize(row)[1:], row) == {
        "comment": "one\ntwo\rthree\tfour five",
        "controls": "\a\b\v",
        "symbols": '"\\$?',
        "hex": "HELLO",
    }


def test_parse_decodes_utf8_hex_escapes():
    row = r'add comment="\D0\BF\D1\80\D0\B8"'
    assert parse_attrs(tokenize(row)[1:], row)["comment"] == "при"
    assert quote("при") == r'"\D0\BF\D1\80\D0\B8"'


@pytest.mark.parametrize(
    "value",
    ["при", "\a\b\v", "\x1b", "\x0c", "\x7f", "\udcff", "one;two[three]$four?five", '"quoted\\"'],
)
def test_quote_round_trips_through_parser(value):
    row = f"add comment={quote(value)}"
    assert parse_attrs(tokenize(row)[1:], row)["comment"] == value


def test_quote_escapes_control_and_stray_bytes():
    assert quote("\x1b") == r'"\1B"'
    assert parse_attrs(tokenize(r'add comment="\f"')[1:], r'add comment="\f"')["comment"] == "\udcff"
    assert quote("\udcff") == r'"\FF"'


@pytest.mark.parametrize(
    "row",
    [
        'add comment="unterminated',
        r'add comment="unknown\xescape"',
        r'add comment="lowercase\4ahex"',
        "add comment=trailing\\",
    ],
)
def test_tokenize_rejects_invalid_syntax(row):
    with pytest.raises(RouterOSParseError):
        tokenize(row)


@pytest.mark.parametrize("tokens", [["missing"], ["=empty"], ["name=one", "name=two"]])
def test_parse_attrs_rejects_invalid_attributes(tokens):
    with pytest.raises(RouterOSParseError):
        parse_attrs(tokens, "add " + " ".join(tokens))


@pytest.mark.parametrize(
    "row, expected",
    [
        ('add name="two words"', 'remove name="two words"'),
        (r'add name="one\$two\?three"', r'remove name="one\$two?three"'),
        (r'add name="\D0\BF\D1\80\D0\B8"', r'remove name="\D0\BF\D1\80\D0\B8"'),
        ("add name=wan#primary", "remove name=wan#primary"),
        ('set ether1 name="two words"', 'remove name="two words"'),
        ('set [ find default-name=ether1 ] name="two words"', 'remove name="two words"'),
        ("set [ find name=legacy ] disabled=yes", "remove name=legacy"),
    ],
)
def test_remove_by_key_uses_routeros_values(row, expected):
    diff = {Op.ADDED: [], Op.REMOVED: [{"row": row}]}
    assert list(change((), diff)) == [(True, expected, None)]


def test_ignore_by_key_preserves_escaped_values():
    row = r'add comment=DHCP local-address=192.0.2.1 name="one\$two\?three"'
    assert _normalize_command(row) == r'add comment=DHCP name="one\$two?three"'


def test_ignore_by_key_preserves_set_selector():
    assert _normalize_command('set ether1 comment=DHCP disabled=yes name="two words"') == (
        'add ether1 comment=DHCP name="two words"'
    )
    assert _normalize_command("set [ find default-name=ether1 ] comment=DHCP disabled=yes") == (
        "add [ find default-name=ether1 ] comment=DHCP"
    )
