from argparse import ArgumentError
from importlib.metadata import EntryPoint
from unittest.mock import Mock

import pytest

from annet.argparse import Arg, ArgParser, _get_meta, subcommand


@subcommand(Arg("--name", default="world"))
def hello_command(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"


@subcommand(is_group=True)
def example_group() -> None:
    """Example commands."""


@subcommand(parent=example_group)
def example_group_child() -> str:
    """Example child command."""
    return "child result"


def test_plugin_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    entry_point = EntryPoint(name="hello", value=f"{__name__}:hello_command", group="annet.commands")
    discover = Mock(return_value=[entry_point])
    monkeypatch.setattr("annet.argparse.entry_points", discover)
    parser = ArgParser()
    parser.add_commands(parser.find_entry_point_commands())
    monkeypatch.setattr(parser, "argv", lambda: ["hello", "--name", "Alice"])

    assert parser.dispatch() == "Hello, Alice!"
    assert "hello" in parser.format_help()
    assert "Say hello." in parser.format_help()
    discover.assert_called_once_with(group="annet.commands")


def test_no_plugins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("annet.argparse.entry_points", Mock(return_value=[]))

    assert list(ArgParser.find_entry_point_commands()) == []


@pytest.mark.parametrize("value", [object(), lambda: None])
def test_invalid_plugin(monkeypatch: pytest.MonkeyPatch, value: object) -> None:
    entry_point = Mock(value="plugin:hello")
    entry_point.name = "hello"
    entry_point.load.return_value = value
    monkeypatch.setattr("annet.argparse.entry_points", Mock(return_value=[entry_point]))

    with pytest.raises(TypeError, match="decorated with @subcommand"):
        list(ArgParser.find_entry_point_commands())


def test_plugin_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    entry_point = Mock()
    entry_point.load.side_effect = ImportError("Missing plugin dependency")
    monkeypatch.setattr("annet.argparse.entry_points", Mock(return_value=[entry_point]))

    with pytest.raises(ImportError, match="Missing plugin dependency"):
        list(ArgParser.find_entry_point_commands())


@pytest.mark.parametrize("name", ["hello", "help"])
def test_command_name_conflict(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    entry_point = EntryPoint(name=name, value=f"{__name__}:hello_command", group="annet.commands")
    monkeypatch.setattr("annet.argparse.entry_points", Mock(return_value=[entry_point]))
    parser = ArgParser()

    with pytest.raises((ValueError, ArgumentError), match="reserved|conflicting subparser"):
        commands = list(parser.find_entry_point_commands())
        parser.add_commands([*commands, *commands])


def test_plugin_aliases_preserve_builtin_name(monkeypatch: pytest.MonkeyPatch) -> None:
    entry_points = [
        EntryPoint(name=name, value=f"{__name__}:hello_command", group="annet.commands") for name in ("hello", "greet")
    ]
    monkeypatch.setattr("annet.argparse.entry_points", Mock(return_value=entry_points))
    original_name = _get_meta(hello_command).cmd_name
    parser = ArgParser()
    parser.add_commands([hello_command, *parser.find_entry_point_commands()])

    assert _get_meta(hello_command).cmd_name == original_name
    for name in (original_name, "hello", "greet"):
        monkeypatch.setattr(parser, "argv", Mock(return_value=[name]))
        assert parser.dispatch() == "Hello, world!"


def test_plugin_conflicts_with_builtin(monkeypatch: pytest.MonkeyPatch) -> None:
    entry_point = EntryPoint(name="hello-command", value=f"{__name__}:hello_command", group="annet.commands")
    monkeypatch.setattr("annet.argparse.entry_points", Mock(return_value=[entry_point]))
    parser = ArgParser()

    with pytest.raises((ValueError, ArgumentError), match="conflicting subparser"):
        parser.add_commands([hello_command, *parser.find_entry_point_commands()])


def test_group_aliases(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    entry_points = [
        EntryPoint(name=name, value=f"{__name__}:example_group", group="annet.commands")
        for name in ("example", "alias")
    ]
    monkeypatch.setattr("annet.argparse.entry_points", Mock(return_value=entry_points))
    parser = ArgParser()
    parser.add_commands([example_group_child, *parser.find_entry_point_commands()])

    for name in ("example", "alias"):
        monkeypatch.setattr(parser, "argv", Mock(return_value=[name, "child"]))
        assert parser.dispatch() == "child result"
        monkeypatch.setattr(parser, "argv", Mock(return_value=[name, "--help"]))
        with pytest.raises(SystemExit) as error:
            parser.dispatch()
        assert error.value.code == 0
        assert "Example child command." in capsys.readouterr().out
        monkeypatch.setattr(parser, "argv", Mock(return_value=[name]))
        parser.dispatch()
        assert "Example child command." in capsys.readouterr().out
