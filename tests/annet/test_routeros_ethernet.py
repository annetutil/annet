from collections import OrderedDict as odict

import pytest

from annet.rulebook.routeros.ethernet import EthernetSet, EthernetSetParseError, diff, parse_set


def _pre(*rows: str) -> odict:
    return odict(
        (
            row,
            {
                "match": {"attrs": {"diff_logic": diff}},
                "subtree": odict(),
            },
        )
        for row in rows
    )


def test_parse_default_name_selector_and_attributes():
    parsed = parse_set('set [ find default-name="ether 1" ] name=uplink comment="WAN uplink" disabled=no l2mtu=1598')

    assert parsed == EthernetSet(
        identity="ether 1",
        attrs={"name": "uplink", "comment": "WAN uplink", "disabled": "no", "l2mtu": "1598"},
    )


def test_parse_running_positional_selector():
    parsed = parse_set('set ether1 comment="WAN uplink" disabled=no', allow_positional=True)

    assert parsed == EthernetSet(identity="ether1", attrs={"comment": "WAN uplink", "disabled": "no"})


def test_parse_compact_selector_without_spaces():
    # generators commonly emit the selector without inner spaces
    parsed = parse_set('set [find default-name=ether1] comment="uplink [core] 1"')

    assert parsed == EthernetSet(identity="ether1", attrs={"comment": "uplink [core] 1"})


def test_parse_hash_as_data_instead_of_shlex_comment():
    parsed = parse_set("set [find default-name=ether1] comment=wan#primary disabled=no")

    assert parsed == EthernetSet(identity="ether1", attrs={"comment": "wan#primary", "disabled": "no"})


@pytest.mark.parametrize(
    "row",
    [
        "set",
        "set ether1 comment=uplink",
        "set [ find name=ether1 ] comment=uplink",
        "set [ find default-name=ether1 comment=uplink",
        "set [ find default-name=ether1 ] default-name=ether2",
        "set [ find default-name=ether1 ] comment=first comment=second",
        "set [ find default-name=ether1 ] !comment",
        "set [ find default-name=ether1 ] invalid-token",
    ],
)
def test_parse_rejects_missing_ambiguous_or_malformed_identity(row):
    with pytest.raises(EthernetSetParseError):
        parse_set(row)


def test_diff_rejects_numeric_running_selector():
    old_row = "set 0 comment=first"
    desired_row = "set [ find default-name=ether1 ] comment=first"

    with pytest.raises(EthernetSetParseError, match="Expected a 'find default-name=...' selector"):
        diff(odict({old_row: odict()}), odict({desired_row: odict()}), _pre(old_row, desired_row))


def test_diff_rejects_duplicate_running_identity():
    old_rows = odict(
        {
            "set ether1 comment=first": odict(),
            "set [ find default-name=ether1 ] comment=second": odict(),
        }
    )
    desired_row = "set [ find default-name=ether1 ] comment=first"
    new_rows = odict({desired_row: odict()})

    with pytest.raises(EthernetSetParseError, match="Duplicate default-name 'ether1' in running"):
        diff(old_rows, new_rows, _pre(*old_rows, desired_row))


def test_diff_rejects_duplicate_desired_identity():
    old_row = "set [ find default-name=ether1 ] comment=first"
    old_rows = odict({old_row: odict()})
    new_rows = odict(
        {
            "set [ find default-name=ether1 ] comment=first": odict(),
            "set [ find default-name=ether1 ] comment=second": odict(),
        }
    )

    with pytest.raises(EthernetSetParseError, match="Duplicate default-name 'ether1' in desired"):
        diff(old_rows, new_rows, _pre(old_row, *new_rows))
