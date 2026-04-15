import re
from collections import OrderedDict
from unittest import mock

import annet.vendors
from annet.annlib.command import Command, Question
from annet.annlib.rbparser.deploying import Answer, MakeMessageMatcher
from annet.deploy import apply_deploy_rulebook
from annet.patching import PatchTree
from annet.rulebook.deploying import compile_deploying_text
from tests import make_hw_stub


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
                        "timeout": 30,
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
                        "ignore": [],
                        "regexp": re.compile("^crypto\\s+key\\s+generate\\s+rsa(?:\\s|$)"),
                    },
                    "children": OrderedDict(),
                },
            ),
        ]
    )

    assert res == expected


def test_deploying_rulebook_ignores_nesting():
    """Test that apply_deploy_rulebook correctly processes block and command structure."""
    # Mock HardwareView
    text = """
block
    dialog: Question? ::: Y
command
    dialog: Question? ::: Y
    """
    rules = compile_deploying_text(text, "huawei")
    hw = make_hw_stub("huawei")

    # Create the PatchTree with block and command structure
    p = PatchTree()
    p.add("block", {})
    p.itms[-1].child = PatchTree()
    p.itms[-1].child.add("command", {})
    p.itms[-1].child.add("quit", {})
    p.add("command", {})
    p.itms[-1].child = PatchTree()
    p.itms[-1].child.add("subcommand", {})
    p.itms[-1].child.add("quit", {})

    # Expected result from apply_deploy_rulebook
    expected = [
        Command(cmd="system-view", questions=[], timeout=30, read_timeout=30),
        Command(cmd="block", questions=[Question(question="Question?", answer="Y")], timeout=30, read_timeout=None),
        Command(cmd="command", questions=[Question(question="Question?", answer="Y")], timeout=30, read_timeout=None),
        Command(cmd="quit", questions=[], timeout=30, read_timeout=None),
        Command(cmd="command", questions=[Question(question="Question?", answer="Y")], timeout=30, read_timeout=None),
        Command(cmd="subcommand", questions=[], timeout=30, read_timeout=None),
        Command(cmd="quit", questions=[], timeout=30, read_timeout=None),
        Command(cmd="q", questions=[], timeout=30, read_timeout=30),
    ]

    # Mock get_rulebook to return our compiled rules
    with mock.patch("annet.deploy.get_rulebook") as mock_get_rulebook:
        mock_get_rulebook.return_value = {
            "deploying": rules,
            "patching": {},
            "ordering": None,
            "texts": {
                "patching": "",
                "ordering": "",
                "deploying": text,
            },
        }

        # Apply deploy rulebook
        formatter = annet.vendors.registry_connector.get().match(hw).make_formatter(indent="")
        result = apply_deploy_rulebook(hw, formatter.cmd_paths(p), do_finalize=False, do_commit=False)

    assert len(result) == len(expected)
    for actual, exp in zip(result, expected):
        assert actual.cmd == exp.cmd
        assert actual.questions == exp.questions
        assert actual.timeout == exp.timeout
        assert actual.read_timeout == exp.read_timeout
