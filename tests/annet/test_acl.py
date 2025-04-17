import re
import textwrap
from collections import OrderedDict

import pytest
from annet import rulebook
from annet.annlib.rbparser.acl import compile_acl_text

from annet import patching, tabparser
from annet.vendors import registry_connector

from .. import make_hw_stub
from . import MockDevice, patch_data


@pytest.fixture
def device():
    return MockDevice("Juniper QFX10016", "JUNOS 18.4R3.3", "jun10")


def check_attrs(attrs, direct_regexp, reverse_regexp, vendor, cant_delete=[False], prio=0, generator_names=None, context=None):
    if generator_names == None:
        generator_names = []
    if context == None:
        context = {}
    assert set(attrs.keys()) == {'cant_delete', 'prio', 'reverse_regexp', 'direct_regexp', 'generator_names', 'vendor', 'context'}
    assert attrs['cant_delete'] == cant_delete
    assert attrs['prio'] == prio
    assert attrs['direct_regexp'] == direct_regexp
    assert attrs['reverse_regexp'] == reverse_regexp
    assert attrs['generator_names'] == generator_names
    assert attrs['vendor'] == vendor
    assert attrs['context'] == context


def test_compile_simple_local_acl_text(device):
    text = """
protocols
    mpls
        path *
            ~
"""
    acl_rule = compile_acl_text(
        text=text,
        vendor=device.hw.vendor,
    )

    assert acl_rule is not None
    assert set(acl_rule.keys()) == {'global', 'local'}
    assert acl_rule['global'] == OrderedDict()

    local_rule = acl_rule['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'protocols'}

    protocols_rule = local_rule['protocols']
    assert protocols_rule is not None
    assert set(protocols_rule.keys()) == {'attrs', 'type', 'children'}
    assert protocols_rule['type'] == 'normal'
    check_attrs(
        attrs=protocols_rule['attrs'],
        direct_regexp=re.compile('^protocols(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+protocols(?:\\s|$)'),
        vendor=device.hw.vendor,
        context={},
    )

    children = protocols_rule['children']
    assert children is not None
    assert set(children) == {'global', 'local'}
    assert children['global'] == OrderedDict()

    local_rule = children['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'mpls'}

    mpls_rule = local_rule['mpls']
    assert mpls_rule is not None
    assert set(mpls_rule.keys()) == {'attrs', 'type', 'children'}
    assert mpls_rule['type'] == 'normal'
    check_attrs(
        attrs=mpls_rule['attrs'],
        direct_regexp=re.compile('^mpls(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+mpls(?:\\s|$)'),
        vendor=device.hw.vendor,
    )

    children = mpls_rule['children']
    assert children is not None
    assert set(children) == {'global', 'local'}
    assert children['global'] == OrderedDict()

    local_rule = children['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'path *'}

    path_rule = local_rule['path *']
    assert path_rule is not None
    assert set(path_rule.keys()) == {'attrs', 'type', 'children'}
    assert path_rule['type'] == 'normal'
    check_attrs(
        attrs=path_rule['attrs'],
        direct_regexp=re.compile('^path\\s+([^\\s]+)(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+path\\s+([^\\s]+)(?:\\s|$)'),
        vendor=device.hw.vendor,
    )

    children = path_rule['children']
    assert children is not None
    assert children['global'] == OrderedDict()

    local_rule = children['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'~'}

    tilda_rule = local_rule['~']
    assert tilda_rule is not None
    assert set(tilda_rule.keys()) == {'attrs', 'type', 'children'}
    assert tilda_rule['type'] == 'normal'
    assert tilda_rule['children'] == {'local': OrderedDict(), 'global': OrderedDict()}
    check_attrs(
        attrs=tilda_rule['attrs'],
        direct_regexp=re.compile('^(.+)'),
        reverse_regexp=re.compile('^delete\\s+(.+)'),
        vendor=device.hw.vendor,
    )


def test_compile_simple_global_acl_text(device):
    text = """
protocols
    mpls
        ~                     %global=1
"""

    acl_rule = compile_acl_text(
        text=text,
        vendor=device.hw.vendor,
    )

    assert acl_rule is not None
    assert set(acl_rule.keys()) == {'global', 'local'}
    assert acl_rule['global'] == OrderedDict()

    local_rule = acl_rule['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'protocols'}

    protocols_rule = local_rule['protocols']
    assert protocols_rule is not None
    assert set(protocols_rule.keys()) == {'attrs', 'type', 'children'}
    assert protocols_rule['type'] == 'normal'
    check_attrs(
        attrs=protocols_rule['attrs'],
        direct_regexp=re.compile('^protocols(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+protocols(?:\\s|$)'),
        vendor=device.hw.vendor,
        context={},
    )

    children = protocols_rule['children']
    assert children is not None
    assert set(children) == {'global', 'local'}
    assert children['global'] == OrderedDict()

    local_rule = children['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'mpls'}

    mpls_rule = local_rule['mpls']
    assert mpls_rule is not None
    assert set(mpls_rule.keys()) == {'attrs', 'type', 'children'}
    assert mpls_rule['type'] == 'normal'
    check_attrs(
        attrs=mpls_rule['attrs'],
        direct_regexp=re.compile('^mpls(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+mpls(?:\\s|$)'),
        vendor=device.hw.vendor,
        context={},
    )

    children = mpls_rule['children']
    assert children is not None
    assert set(children) == {'global', 'local'}
    assert children['local'] == OrderedDict()

    global_rule = children['global']
    assert global_rule is not None
    assert set(global_rule.keys()) == {'~'}

    tilda_rule = global_rule['~']
    assert tilda_rule is not None
    assert set(tilda_rule.keys()) == {'attrs', 'type', 'children'}
    assert tilda_rule['type'] == 'normal'
    assert tilda_rule['children'] is None
    check_attrs(
        attrs=tilda_rule['attrs'],
        direct_regexp=re.compile('^(.+)'),
        reverse_regexp=re.compile('^delete\\s+(.+)'),
        vendor=device.hw.vendor,
        context={},
    )


def test_merged_global_and_local_acl_texts(device):
    merged_text = """
protocols                    %cant_delete=1
    mpls
        ~                     %global=1
protocols
    mpls
        path *
            ~
"""
    acl_rule = compile_acl_text(
        text=merged_text,
        vendor=device.hw.vendor,
    )

    assert acl_rule is not None
    assert set(acl_rule.keys()) == {'global', 'local'}
    assert acl_rule['global'] == OrderedDict()

    local_rule = acl_rule['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'protocols'}

    protocols_rule = local_rule['protocols']
    assert protocols_rule is not None
    assert set(protocols_rule.keys()) == {'attrs', 'type', 'children'}
    assert protocols_rule['type'] == 'normal'
    check_attrs(
        attrs=protocols_rule['attrs'],
        direct_regexp=re.compile('^protocols(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+protocols(?:\\s|$)'),
        cant_delete=[True, False],
        vendor=device.hw.vendor,
    )

    children = protocols_rule['children']
    assert children is not None
    assert set(children) == {'global', 'local'}
    assert children['global'] == OrderedDict()

    local_rule = children['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'mpls'}

    mpls_rule = local_rule['mpls']
    assert mpls_rule is not None
    assert set(mpls_rule.keys()) == {'attrs', 'type', 'children'}
    assert mpls_rule['type'] == 'normal'
    check_attrs(
        attrs=mpls_rule['attrs'],
        direct_regexp=re.compile('^mpls(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+mpls(?:\\s|$)'),
        cant_delete=[False, False],
        vendor=device.hw.vendor,
    )

    children = mpls_rule['children']
    assert children is not None
    assert set(children) == {'global', 'local'}

    global_rule = children['global']
    assert global_rule is not None
    assert set(global_rule.keys()) == {'~'}

    tilda_rule = global_rule['~']
    assert tilda_rule is not None
    assert set(tilda_rule.keys()) == {'attrs', 'type', 'children'}
    assert tilda_rule['type'] == 'normal'
    assert tilda_rule['children'] is None

    local_rule = children['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'path *'}

    path_rule = local_rule['path *']
    assert path_rule is not None
    assert set(path_rule.keys()) == {'attrs', 'type', 'children'}
    assert path_rule['type'] == 'normal'
    check_attrs(
        attrs=path_rule['attrs'],
        direct_regexp=re.compile('^path\\s+([^\\s]+)(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+path\\s+([^\\s]+)(?:\\s|$)'),
        vendor=device.hw.vendor,
    )

    children = path_rule['children']
    assert children is not None
    assert children['global'] == OrderedDict()

    local_rule = children['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'~'}

    tilda_rule = local_rule['~']
    assert tilda_rule is not None
    assert set(tilda_rule.keys()) == {'attrs', 'type', 'children'}
    assert tilda_rule['type'] == 'normal'
    assert tilda_rule['children'] == {'local': OrderedDict(), 'global': OrderedDict()}
    check_attrs(
        attrs=tilda_rule['attrs'],
        direct_regexp=re.compile('^(.+)'),
        reverse_regexp=re.compile('^delete\\s+(.+)'),
        vendor=device.hw.vendor,
    )


def test_merged_local_acl_texts(device):
    merged_text = """
protocols
    mpls
        label-switched-path *
            ~
protocols
    mpls
        path *
            ~
    """
    acl_rule = compile_acl_text(
        text=merged_text,
        vendor=device.hw.vendor,
    )

    assert acl_rule is not None
    assert set(acl_rule.keys()) == {'global', 'local'}
    assert acl_rule['global'] == OrderedDict()

    local_rule = acl_rule['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'protocols'}

    protocols_rule = local_rule['protocols']
    assert protocols_rule is not None
    assert set(protocols_rule.keys()) == {'attrs', 'type', 'children'}
    assert protocols_rule['type'] == 'normal'
    check_attrs(
        attrs=protocols_rule['attrs'],
        direct_regexp=re.compile('^protocols(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+protocols(?:\\s|$)'),
        vendor=device.hw.vendor,
    )

    children = protocols_rule['children']
    assert children is not None
    assert set(children) == {'global', 'local'}
    assert children['global'] == OrderedDict()

    local_rule = children['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'mpls'}

    mpls_rule = local_rule['mpls']
    assert mpls_rule is not None
    assert set(mpls_rule.keys()) == {'attrs', 'type', 'children'}
    assert mpls_rule['type'] == 'normal'
    check_attrs(
        attrs=mpls_rule['attrs'],
        direct_regexp=re.compile('^mpls(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+mpls(?:\\s|$)'),
        vendor=device.hw.vendor,
    )

    children = mpls_rule['children']
    assert children is not None
    assert set(children) == {'global', 'local'}
    assert children['global'] == OrderedDict()

    local_rule = children['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'path *', 'label-switched-path *'}

    path_rule = local_rule['path *']
    ls_path_rule = local_rule['label-switched-path *']

    assert path_rule is not None
    assert set(path_rule.keys()) == {'attrs', 'type', 'children'}
    assert path_rule['type'] == 'normal'
    check_attrs(
        attrs=path_rule['attrs'],
        direct_regexp=re.compile('^path\\s+([^\\s]+)(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+path\\s+([^\\s]+)(?:\\s|$)'),
        vendor=device.hw.vendor,
    )

    children = path_rule['children']
    assert children is not None
    assert children['global'] == OrderedDict()

    local_rule = children['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'~'}

    tilda_rule = local_rule['~']
    assert tilda_rule is not None
    assert set(tilda_rule.keys()) == {'attrs', 'type', 'children'}
    assert tilda_rule['type'] == 'normal'
    assert tilda_rule['children'] == {'local': OrderedDict(), 'global': OrderedDict()}
    check_attrs(
        attrs=tilda_rule['attrs'],
        direct_regexp=re.compile('^(.+)'),
        reverse_regexp=re.compile('^delete\\s+(.+)'),
        vendor=device.hw.vendor,
    )

    assert ls_path_rule is not None
    assert set(ls_path_rule.keys()) == {'attrs', 'type', 'children'}
    assert ls_path_rule['type'] == 'normal'
    check_attrs(
        attrs=ls_path_rule['attrs'],
        direct_regexp=re.compile('^label-switched-path\\s+([^\\s]+)(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+label-switched-path\\s+([^\\s]+)(?:\\s|$)'),
        vendor=device.hw.vendor,
    )

    children = ls_path_rule['children']
    assert children is not None
    assert children['global'] == OrderedDict()

    local_rule = children['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'~'}

    tilda_rule = local_rule['~']
    assert tilda_rule is not None
    assert set(tilda_rule.keys()) == {'attrs', 'type', 'children'}
    assert tilda_rule['type'] == 'normal'
    assert tilda_rule['children'] == {'local': OrderedDict(), 'global': OrderedDict()}
    check_attrs(
        attrs=tilda_rule['attrs'],
        direct_regexp=re.compile('^(.+)'),
        reverse_regexp=re.compile('^delete\\s+(.+)'),
        vendor=device.hw.vendor,
    )


def test_merged_global_acl_texts(device):
    merged_text = """
protocols
    mpls
        ~                     %global=1
protocols
    ldp
        ~                     %global=1
    """
    acl_rule = compile_acl_text(
        text=merged_text,
        vendor=device.hw.vendor,
    )

    assert acl_rule is not None
    assert set(acl_rule.keys()) == {'global', 'local'}
    assert acl_rule['global'] == OrderedDict()

    local_rule = acl_rule['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'protocols'}

    protocols_rule = local_rule['protocols']
    assert protocols_rule is not None
    assert set(protocols_rule.keys()) == {'attrs', 'type', 'children'}
    assert protocols_rule['type'] == 'normal'
    check_attrs(
        attrs=protocols_rule['attrs'],
        direct_regexp=re.compile('^protocols(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+protocols(?:\\s|$)'),
        vendor=device.hw.vendor,
    )

    children = protocols_rule['children']
    assert children is not None
    assert set(children) == {'global', 'local'}
    assert children['global'] == OrderedDict()

    local_rule = children['local']
    assert local_rule is not None
    assert set(local_rule.keys()) == {'mpls', 'ldp'}

    mpls_rule = local_rule['mpls']
    ldp_rule = local_rule['ldp']

    assert mpls_rule is not None
    assert set(mpls_rule.keys()) == {'attrs', 'type', 'children'}
    assert mpls_rule['type'] == 'normal'
    check_attrs(
        attrs=mpls_rule['attrs'],
        direct_regexp=re.compile('^mpls(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+mpls(?:\\s|$)'),
        vendor=device.hw.vendor,
    )

    children = mpls_rule['children']
    assert children is not None
    assert set(children) == {'global', 'local'}
    assert children['local'] == OrderedDict()

    global_rule = children['global']
    assert global_rule is not None
    assert set(global_rule.keys()) == {'~'}

    tilda_rule = global_rule['~']
    assert tilda_rule is not None
    assert set(tilda_rule.keys()) == {'attrs', 'type', 'children'}
    assert tilda_rule['type'] == 'normal'
    assert tilda_rule['children'] is None
    check_attrs(
        attrs=tilda_rule['attrs'],
        direct_regexp=re.compile('^(.+)'),
        reverse_regexp=re.compile('^delete\\s+(.+)'),
        vendor=device.hw.vendor,
    )

    assert ldp_rule is not None
    assert set(ldp_rule.keys()) == {'attrs', 'type', 'children'}
    assert ldp_rule['type'] == 'normal'
    check_attrs(
        attrs=ldp_rule['attrs'],
        direct_regexp=re.compile('^ldp(?:\\s|$)'),
        reverse_regexp=re.compile('^delete\\s+ldp(?:\\s|$)'),
        vendor=device.hw.vendor,
    )

    children = ldp_rule['children']
    assert children is not None
    assert set(children) == {'global', 'local'}
    assert children['local'] == OrderedDict()

    global_rule = children['global']
    assert global_rule is not None
    assert set(global_rule.keys()) == {'~'}

    tilda_rule = global_rule['~']
    assert tilda_rule is not None
    assert set(tilda_rule.keys()) == {'attrs', 'type', 'children'}
    assert tilda_rule['type'] == 'normal'
    assert tilda_rule['children'] is None
    check_attrs(
        attrs=tilda_rule['attrs'],
        direct_regexp=re.compile('^(.+)'),
        reverse_regexp=re.compile('^delete\\s+(.+)'),
        vendor=device.hw.vendor,
    )


@pytest.mark.parametrize(
    "name, sample",
    patch_data.get_samples(dirname="annet/test_acl")
)
def test_acl(ann_connectors, name, sample):
    vendor = sample["vendor"].lower()
    hw = make_hw_stub(vendor)
    acl_text = textwrap.dedent(sample["acl"])
    input_text = textwrap.dedent(sample["input"])
    output_text = textwrap.dedent(sample["output"])

    fmtr = registry_connector.get().match(hw).make_formatter()
    rules = compile_acl_text(acl_text, vendor, allow_ignore=True)
    tree = tabparser.parse_to_tree(text=input_text, splitter=fmtr.split)

    tree = patching.apply_acl(tree, rules)
    result_text = fmtr.join(tree)
    result_text, output_text = result_text.strip(), output_text.strip()
    assert result_text == output_text
