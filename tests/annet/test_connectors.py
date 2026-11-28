from unittest.mock import Mock

import pytest

from annet.connectors import AdapterWithConfig, AdapterWithName, get_connector_from_config


class ExampleAdapter(AdapterWithConfig["ExampleAdapter"], AdapterWithName):
    def __init__(self, user: str) -> None:
        self.user = user

    @classmethod
    def name(cls) -> str:
        return "example"

    @classmethod
    def with_config(cls, **kwargs) -> "ExampleAdapter":
        return cls(**kwargs)


def test_adapter_import_skips_discovery(monkeypatch):
    params = {"user": "automation"}
    monkeypatch.setattr(
        "annet.connectors.get_context",
        lambda: {"fetcher": {"adapter": f"{__name__}:ExampleAdapter", "params": params}},
    )
    discover = Mock(side_effect=AssertionError("unexpected adapter discovery"))

    adapter, actual_params = get_connector_from_config("fetcher", discover, expected_type=ExampleAdapter)

    assert isinstance(adapter, ExampleAdapter)
    assert adapter.user == "automation"
    assert actual_params == params


@pytest.mark.parametrize("lazy", [False, True])
def test_adapter_name_resolves_registered_class(monkeypatch, lazy):
    monkeypatch.setattr(
        "annet.connectors.get_context",
        lambda: {"fetcher": {"adapter": "example", "params": {"user": "automation"}}},
    )
    candidates = [ExampleAdapter]

    adapter, _ = get_connector_from_config("fetcher", (lambda: candidates) if lazy else candidates)

    assert isinstance(adapter, ExampleAdapter)
    assert adapter.user == "automation"


def test_adapter_import_rejects_wrong_class(monkeypatch):
    monkeypatch.setattr("annet.connectors.get_context", lambda: {"fetcher": {"adapter": "builtins:str"}})

    with pytest.raises(TypeError, match="must be a subclass of ExampleAdapter"):
        get_connector_from_config("fetcher", [], expected_type=ExampleAdapter)
