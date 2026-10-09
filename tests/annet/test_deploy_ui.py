import curses
from collections.abc import Callable
from unittest import mock

import pytest

from annet.deploy_ui import AskConfirm


@pytest.fixture
def terminal(monkeypatch):
    size = [24, 100]
    keys: list[int | Callable[[], int]] = []
    screen = mock.Mock()
    pads = []

    def getch():
        key = keys.pop(0)
        return key() if callable(key) else key

    def addnstr(y, x, text, count, color):
        assert 0 <= y < size[0]
        assert 0 <= x < size[1]
        assert x + min(len(text), count) < size[1]

    def move(y, x):
        assert 0 <= y < size[0]
        assert 0 <= x < size[1]

    def newpad(height, width):
        assert height > 0 and width > 0
        pad = mock.Mock()
        position = [0, 0]

        def pad_move(y, x):
            assert 0 <= y < height
            assert 0 <= x < width
            position[:] = [y, x]

        def refresh(top, left, y, x, bottom, right):
            assert 0 <= y <= bottom < size[0] - 1
            assert 0 <= x <= right < size[1]
            assert 0 <= top and top + bottom - y < height
            assert 0 <= left and left + right - x < width

        pad.getmaxyx.side_effect = lambda: (height, width)
        pad.getyx.side_effect = lambda: tuple(position)
        pad.move.side_effect = pad_move
        pad.refresh.side_effect = refresh
        pads.append(pad)
        return pad

    screen.getmaxyx.side_effect = lambda: tuple(size)
    screen.getch.side_effect = getch
    screen.addnstr.side_effect = addnstr
    screen.move.side_effect = move
    monkeypatch.setattr(curses, "initscr", lambda: screen)
    monkeypatch.setattr(curses, "newpad", newpad)
    monkeypatch.setattr(curses, "color_pair", lambda pair: pair)
    for name in ("start_color", "use_default_colors", "init_pair", "noecho", "echo", "cbreak", "nocbreak", "endwin"):
        monkeypatch.setattr(curses, name, mock.Mock())
    monkeypatch.setattr(curses, "curs_set", mock.Mock(return_value=1))
    return size, keys, screen, pads


@pytest.mark.parametrize("new_size", [(23, 100), (5, 20), (1, 1), (50, 200)])
def test_resize_keeps_confirmation_open(terminal, new_size):
    size, keys, screen, _ = terminal

    def resize():
        size[:] = new_size
        return curses.KEY_RESIZE

    keys.extend([resize, curses.KEY_DOWN, ord("y")])
    ask = AskConfirm("\n".join(f"+ line {n}" for n in range(40)))
    assert ask.loop() == "y"
    assert 0 <= ask.top <= max(0, ask.rows - max(1, new_size[0] - 1))
    assert screen.addnstr.call_args_list


@pytest.mark.parametrize(
    "navigation, expected_top, expected_left",
    [
        ([curses.KEY_DOWN], 1, 0),
        ([curses.KEY_DOWN, curses.KEY_UP], 0, 0),
        ([curses.KEY_PPAGE], 0, 0),
        ([curses.KEY_NPAGE], 23, 0),
        ([curses.KEY_END], 77, 0),
        ([curses.KEY_END, curses.KEY_HOME], 0, 0),
        ([curses.KEY_RIGHT], 0, 1),
        ([curses.KEY_RIGHT, curses.KEY_LEFT], 0, 0),
    ],
)
def test_navigation_scrolls_viewport(terminal, navigation, expected_top, expected_left):
    _, keys, _, _ = terminal
    keys.extend([*navigation, ord("y")])
    ask = AskConfirm("\n".join("+ " + "x" * 150 for _ in range(100)))
    assert ask.loop() == "y"
    assert (ask.top, ask.left) == (expected_top, expected_left)


@pytest.mark.parametrize("text", ["", "\n", "+ short"])
def test_short_text_stays_in_bounds(terminal, text):
    _, keys, _, _ = terminal
    keys.extend([curses.KEY_DOWN, curses.KEY_END, curses.KEY_RIGHT, ord("y")])
    ask = AskConfirm(text)
    assert ask.loop() == "y"
    assert (ask.top, ask.left) == (0, 0)


def test_switch_to_short_commands_after_scrolling(terminal):
    _, keys, _, _ = terminal
    keys.extend([curses.KEY_END, ord("a"), ord("y")])
    ask = AskConfirm("\n".join("+ change" for _ in range(100)), alternative_text="command")
    assert ask.loop() == "y"
    assert ask.text[0] == "command"
    assert ask.top == 0


@pytest.mark.parametrize("key, answer", [(ord("q"), "exit"), (ord("y"), "y"), (ord("f"), "force-yes")])
def test_confirmation_answers(terminal, key, answer):
    _, keys, _, _ = terminal
    keys.append(key)
    assert AskConfirm("+ change", allow_force_yes=True).loop() == answer


def test_confirmation_uses_terminal_background(terminal):
    _, keys, _, _ = terminal
    keys.append(ord("q"))
    assert AskConfirm("+ change").loop() == "exit"
    curses.use_default_colors.assert_called_once_with()
    assert all(call.args[2] == -1 for call in curses.init_pair.call_args_list)


@pytest.mark.parametrize("search_keys, expected_row", [([], 40), ([ord("n")], 70), ([ord("n"), ord("N")], 40)])
def test_search_after_scrolling(terminal, search_keys, expected_row):
    _, keys, screen, pads = terminal
    screen.getstr.return_value = b"needle"
    keys.extend([curses.KEY_NPAGE, ord("/"), *search_keys, ord("y")])
    lines = ["+ needle" if n in (40, 70) else "+ other" for n in range(100)]
    ask = AskConfirm("\n".join(lines))
    assert ask.loop() == "y"
    assert pads[-1].getyx()[0] == expected_row
    assert ask.top <= expected_row < ask.top + 23
