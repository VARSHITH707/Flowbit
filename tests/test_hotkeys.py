import pytest

from voicetype.hotkeys import Hotkeys, parse


def make():
    ev = []
    h = Hotkeys(lambda: ev.append("start"), lambda: ev.append("stop"), lambda: ev.append("toggle"),
                lambda: ev.append("cancel"), lambda: ev.append("settings"))
    return h, ev


def drain(h):
    out = []
    while not h._q.empty():
        out.append(h._q.get())
    return out


def test_parse_valid_and_invalid():
    assert parse("ctrl+alt+space") == (frozenset({"ctrl", "alt"}), "space")
    assert parse("Ctrl+Windows") == (frozenset({"ctrl", "windows"}), None)
    for bad in ("", "ctrl+a+b", "ctrl+banana"):
        with pytest.raises(ValueError):
            parse(bad)


def test_hold_start_stop_and_repeat_ignored():
    h, _ = make()
    h._key_down("ctrl"); h._key_down("alt"); h._key_down("d"); h._key_down("d")
    assert drain(h) == ["start"]
    h._key_up("d")
    assert drain(h) == ["stop"]
    h._key_up("alt"); h._key_up("ctrl")
    assert drain(h) == []


def test_combo_needs_exact_modifiers():
    h, _ = make()
    h._key_down("ctrl"); h._key_down("alt"); h._key_down("shift"); h._key_down("space")
    assert "toggle" not in drain(h)
    h._down.clear()
    h._key_down("ctrl"); h._key_down("alt"); h._key_down("space")
    assert drain(h) == ["toggle"]


def test_no_stuck_state_after_release():
    h, _ = make()
    for k in ("ctrl", "alt", "space"):
        h._key_down(k)
    for k in ("space", "alt", "ctrl"):
        h._key_up(k)
    drain(h)
    h._key_down("esc")
    assert drain(h) == ["cancel"]


def test_chord_key_is_swallowed_only_inside_the_chord():
    h, _ = make()
    assert h._key_down("d") is False          # plain 'd' typed normally
    assert h._key_up("d") is False
    h._key_down("ctrl"); h._key_down("alt")
    assert h._key_down("d") is True           # hold chord's letter must not reach the app
    assert h._key_down("d") is True           # auto-repeat is swallowed too
    assert h._key_up("d") is True             # matching key-up swallowed, so no stuck key
    assert h._key_up("d") is False            # and only once
    assert h._key_down("space") is True       # toggle chord (ctrl+alt+space)
    assert h._key_up("space") is True


def test_bare_cancel_key_is_never_swallowed():
    h, _ = make()
    assert h._key_down("esc") is False
    assert h._key_up("esc") is False
    drain(h)


def test_modifiers_are_never_swallowed():
    h, _ = make()
    assert h._key_down("ctrl") is False and h._key_down("alt") is False
    assert h._key_up("alt") is False and h._key_up("ctrl") is False
