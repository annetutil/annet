import re
from collections import OrderedDict
from unittest import mock

from annet.annlib.rbparser.deploying import Answer, MakeMessageMatcher
from annet.rulebook.deploying import compile_deploying_text


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


def test_delay_after_command(ann_connectors):
    from annet.annlib.netdev.views.hardware import HardwareView
    from annet.deploy import apply_deploy_rulebook
    from annet.rulebook.deploying import match_deploy_rule

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
    import pytest
    from valkit import ValidatorError

    with pytest.raises(ValidatorError):
        compile_deploying_text("undo peer *$ %delay_after=-1", "sitonica")
