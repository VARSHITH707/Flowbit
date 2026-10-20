import pytest

from voicetype import insertion as ins


@pytest.fixture
def fake(monkeypatch):
    """Fake keystrokes, clipboard and text box: the real clipboard is never touched."""
    state = {"sent": 0, "restored": None, "clip": None, "seq": []}
    monkeypatch.setattr(ins, "_send", lambda ev: state.__setitem__("sent", state["sent"] + (ev == ins.CTRL_V)))
    monkeypatch.setattr(ins, "set_clipboard", lambda t: state.__setitem__("clip", t))
    monkeypatch.setattr(ins, "restore_clipboard", lambda items: state.__setitem__("restored", items))
    monkeypatch.setattr(ins.time, "sleep", lambda s: None)

    def occurrences(text):
        return state["seq"].pop(0) if state["seq"] else state.get("last")
    monkeypatch.setattr(ins, "_occurrences", occurrences)
    return state


def test_paste_confirmed_first_try(fake):
    fake["seq"] = [0]          # before: not in the box
    fake["last"] = 1           # after Ctrl+V it appears
    ins.paste_text("hello", saved=[("x", "old")])
    assert fake["sent"] == 1 and fake["restored"] == [("x", "old")]


def test_lost_paste_is_reported_never_resent(fake, monkeypatch):
    fake["seq"] = [0]
    monkeypatch.setattr(ins, "_wait_landed", lambda *a: False)
    with pytest.raises(OSError, match="could not be confirmed"):
        ins.paste_text("hello", saved=[("x", "old")])
    assert fake["sent"] == 1  # never a second Ctrl+V: that caused duplicates
    assert fake["restored"] == [("x", "old")]


def test_unreadable_app_behaves_as_before(fake, monkeypatch):
    fake["seq"] = [None]       # app does not expose its text
    monkeypatch.setattr(ins, "_wait_landed", lambda *a: pytest.fail("must not wait on an unreadable app"))
    ins.paste_text("hello", saved=[])
    assert fake["sent"] == 1


def test_already_present_text_needs_a_new_copy(fake):
    fake["seq"] = [2, 2, 2, 3]  # same sentence already twice in the box; only a third copy counts
    ins.paste_text("hello", saved=[])
    assert fake["sent"] == 1


def test_focus_on_a_button_copies_instead_of_losing_text(monkeypatch):
    calls = {}
    monkeypatch.setattr(ins, "foreground", lambda: 42)
    monkeypatch.setattr(ins.win32gui, "IsWindow", lambda h: True)
    monkeypatch.setattr(ins, "focused_kind", lambda: "ButtonControl")
    monkeypatch.setattr(ins, "set_clipboard", lambda t: calls.setdefault("clip", t))
    monkeypatch.setattr(ins, "paste_text", lambda *a: pytest.fail("must not paste into a button"))
    r = ins.insert("hello", 42)
    assert r.status == "copied" and "No text box" in r.detail and calls["clip"] == "hello"


@pytest.mark.parametrize("kind", ["EditControl", "DocumentControl", None, "PaneControl", "CustomControl"])
def test_text_or_unknown_controls_still_get_the_paste(monkeypatch, kind):
    monkeypatch.setattr(ins, "foreground", lambda: 42)
    monkeypatch.setattr(ins.win32gui, "IsWindow", lambda h: True)
    monkeypatch.setattr(ins, "focused_kind", lambda: kind)
    monkeypatch.setattr(ins, "capture_clipboard", lambda: [])
    pasted = []
    monkeypatch.setattr(ins, "paste_text", lambda text, saved: pasted.append(text))
    assert ins.insert("hello", 42).status == "inserted" and pasted == ["hello"]
