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
    expected = OrderedDict([
        (
            "crypto key generate rsa",
            {
                "attrs": {
                    "apply_logic": mock.ANY,
                    "timeout": 30,
                    "dialogs": OrderedDict([
                        (
                            MakeMessageMatcher("Do you really want to replace them? [yes/no]:"),
                            Answer(text="no", send_nl=True)
                        ),
                        (
                            MakeMessageMatcher("How many bits in the modulus [512]:"),
                            Answer(text="2048", send_nl=True))
                    ]),
                    'ifcontext': [],
                    "ignore": [],
                    "regexp": re.compile("^crypto\\s+key\\s+generate\\s+rsa(?:\\s|$)")
                },
                "children": OrderedDict(),
            },
        ),
    ])

    assert res == expected
