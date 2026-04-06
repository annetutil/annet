import os
from pathlib import Path

from annet.rulebook import RulebookProvider


def test_use_valid_custom_rulebook_module():
    custom_rulebook_module = "tests.annet.test_rulebooks.rulebook"
    provider = RulebookProvider(custom_rulebook_module)

    path_to_rulebook = os.path.dirname(provider.rulebook_module.__file__)
    expected_path_to_rulebook = os.path.join(Path(__file__).parent, "rulebook")

    assert path_to_rulebook == expected_path_to_rulebook
