import re
from collections import OrderedDict
from unittest import mock

import pytest
from valkit import ValidatorError

from annet.annlib.rbparser.deploying import Answer, MakeMessageMatcher
from annet.rulebook.deploying import (
    compile_deploying_text,
    dump_deploy_rulebook,
    match_deploy_rule,
    merge_deploy_rulebooks,
)


def test_compile_deploying_text_cisco_2_dialogs(ann_connectors):
    text = """crypto key generate rsa
        dialog: Do you really want to replace them? [yes/no]: ::: no
        dialog: How many bits in the modulus [512]: ::: 2048
    """
    res = compile_deploying_text(text, "cisco")
    expected = OrderedDict(
        [
            (
                "crypto key generate rsa",
                {
                    "attrs": {
                        "apply_logic": mock.ANY,
                        "apply_logic_name": "annet.rulebook.common.apply",
                        "dialogs": OrderedDict(
                            [
                                (
                                    MakeMessageMatcher("Do you really want to replace them? [yes/no]:"),
                                    Answer(text="no", send_nl=True),
                                ),
                                (
                                    MakeMessageMatcher("How many bits in the modulus [512]:"),
                                    Answer(text="2048", send_nl=True),
                                ),
                            ]
                        ),
                        "ifcontext": [],
                        "regexp": re.compile("^crypto\\s+key\\s+generate\\s+rsa(?:\\s|$)"),
                        "suppress_errors": False,
                        "timeout": 30,
                        "delay_after": 0.0,
                    },
                    "children": OrderedDict(),
                },
            ),
        ]
    )

    assert res == expected


def test_compile_deploying_text_default_timeout(ann_connectors: None) -> None:
    text = """interface *
    description *
commit %timeout=180
save %timeout=30
"""
    for default_timeout in (120, 45.5):
        rules = compile_deploying_text(text, "cisco", default_timeout=default_timeout)
        assert rules["interface *"]["attrs"]["timeout"] == default_timeout
        assert rules["interface *"]["children"]["description *"]["attrs"]["timeout"] == default_timeout
        assert rules["commit %timeout=180"]["attrs"]["timeout"] == 180
        assert rules["save %timeout=30"]["attrs"]["timeout"] == 30

    rules = compile_deploying_text(text, "cisco")
    assert rules["interface *"]["attrs"]["timeout"] == 30
    assert rules["interface *"]["children"]["description *"]["attrs"]["timeout"] == 30


@pytest.mark.parametrize(
    ("text", "cmd_path"),
    [
        ("", ("configure",)),
        ("", ()),
        ("commit %timeout=180", ()),
        ("commit %timeout=180", ("configure",)),
        ("commit %ifcontext=mode:save", ("commit",)),
    ],
)
def test_match_deploy_rule_default_timeout(ann_connectors: None, text: str, cmd_path: tuple[str, ...]) -> None:
    rules = compile_deploying_text(text, "cisco")
    assert match_deploy_rule(rules, cmd_path, {}, default_timeout=120)["attrs"]["timeout"] == 120
    assert match_deploy_rule(rules, cmd_path, {})["attrs"]["timeout"] == 30


def test_match_deploy_rule_preserves_matched_timeout(ann_connectors: None) -> None:
    rules = compile_deploying_text("configure\ncommit %timeout=180\nsave %timeout=30", "cisco", default_timeout=120)
    assert match_deploy_rule(rules, ("configure",), {}, default_timeout=60)["attrs"]["timeout"] == 120
    assert match_deploy_rule(rules, ("commit",), {}, default_timeout=60)["attrs"]["timeout"] == 180
    assert match_deploy_rule(rules, ("save",), {}, default_timeout=60)["attrs"]["timeout"] == 30


@pytest.mark.parametrize("default_timeout", [0, -1, 0.5])
def test_default_timeout_invalid(ann_connectors: None, default_timeout: float) -> None:
    with pytest.raises(ValidatorError):
        compile_deploying_text("", "cisco", default_timeout=default_timeout)
    with pytest.raises(ValidatorError):
        match_deploy_rule(OrderedDict(), ("configure",), {}, default_timeout=default_timeout)


def test_default_timeout_preserves_explicit_timeout_after_merge_and_dump(ann_connectors: None) -> None:
    parent = compile_deploying_text(
        "interface * %timeout=30\n    description * %timeout=30\nparent-only %timeout=30\nordinary", "cisco"
    )
    child = compile_deploying_text("interface *\nchild-only %timeout=30\n    nested %timeout=30\n    implicit", "cisco")
    merged = merge_deploy_rulebooks(parent, child, "cisco")
    rules = compile_deploying_text(dump_deploy_rulebook(merged), "cisco", default_timeout=120)

    for path in (
        ("interface Ethernet1",),
        ("interface Ethernet1", "description test"),
        ("parent-only",),
        ("child-only",),
        ("child-only", "nested"),
    ):
        assert match_deploy_rule(rules, path, {}, default_timeout=120)["attrs"]["timeout"] == 30
    assert match_deploy_rule(rules, ("ordinary",), {}, default_timeout=120)["attrs"]["timeout"] == 120
    assert match_deploy_rule(rules, ("child-only", "implicit"), {}, default_timeout=120)["attrs"]["timeout"] == 120


def test_delay_after_command(ann_connectors):
    from annet.annlib.netdev.views.hardware import HardwareView
    from annet.deploy import apply_deploy_rulebook

    rules = compile_deploying_text("undo peer *$ %delay_after=0.25", "sitonica")
    path = ("bgp 123", "undo peer 2001:db8::1")
    assert match_deploy_rule(rules, path, {})["attrs"]["delay_after"] == 0.25
    assert match_deploy_rule(rules, ("undo peer 2001:db8::1 description",), {})["attrs"]["delay_after"] == 0
    with (
        mock.patch("annet.deploy.get_rulebook", return_value={"deploying": rules}),
        mock.patch("annet.deploy.make_apply_commands", return_value=([], [])),
    ):
        commands = apply_deploy_rulebook(HardwareView("Sitonica SW6850"), {path: {}})
    assert [(cmd.cmd, cmd.delay_after) for cmd in commands] == [("undo peer 2001:db8::1", 0.25)]


def test_delay_after_negative_rejected(ann_connectors):
    with pytest.raises(ValidatorError):
        compile_deploying_text("undo peer *$ %delay_after=-1", "sitonica")
