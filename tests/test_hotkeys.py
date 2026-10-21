import pytest

from voicetype.hotkeys import Hotkeys, parse


def make(**bindings):
    ev = []
    h = Hotkeys(lambda: ev.append("start"), lambda: ev.append("stop"), lambda: ev.append("toggle"),
                lambda: ev.append("cancel"), lambda: ev.append("settings"), on_undo=lambda: ev.append("undo"),
                bindings={"toggle": "ctrl+alt+space", **bindings})  # chord logic tests use a fixed toggle chord
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


def test_undo_hotkey_fires_once():
    h, _ = make()
    h._key_down("ctrl"); h._key_down("alt"); h._key_down("z"); h._key_down("z")  # auto-repeat
    assert drain(h) == ["undo"]


def test_modifier_only_toggle_fires_on_release_without_other_keys():
    h, _ = make(toggle="ctrl+windows")
    h._key_down("ctrl"); h._key_down("windows"); h._key_up("windows"); h._key_up("ctrl")
    assert drain(h) == ["toggle"]
    h._key_down("ctrl"); h._key_down("windows"); h._key_down("d"); h._key_up("d"); h._key_up("windows"); h._key_up("ctrl")
    assert drain(h) == []  # ctrl+win+d (new desktop) must not toggle recording
    h._key_down("ctrl"); h._key_down("shift"); h._key_down("windows"); h._key_up("windows")
    assert drain(h) == []  # extra modifier: not the chord


def test_modifier_only_shortcut_rejected_for_commands_that_need_a_key():
    with pytest.raises(ValueError):
        make(undo="ctrl+alt")


def test_conflicts_catch_editing_keys_and_overlaps():
    from voicetype.hotkeys import DEFAULTS, conflicts
    assert "Undo" in conflicts({**DEFAULTS, "hold": "ctrl+z"})
    assert "overlap" in conflicts({**DEFAULTS, "hold": "ctrl+alt", "toggle": "ctrl+alt+t"})
