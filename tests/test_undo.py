"""Undo Last Insertion: removes Flowbit's text only when it can prove it is exactly that text."""
import contextlib
import sys
import types

import pytest

from voicetype import insertion, undo


class Range:
    def __init__(self, ctl, text):
        self.ctl, self.text = ctl, text

    def FindText(self, text, backward, ignore_case):
        return Range(self.ctl, text) if text in self.ctl.value else None

    def Select(self):
        self.ctl.selection = self.text

    def GetText(self, n):
        return self.text


class TP:
    def __init__(self, ctl):
        self.ctl, self.DocumentRange = ctl, Range(ctl, ctl.value)

    def GetSelection(self):
        return [Range(self.ctl, self.ctl.selection)] if self.ctl.selection else []


class Ctl:
    def __init__(self, value, rid=(1, 2), text_pattern=True):
        self.value, self.rid, self.selection, self.tp = value, rid, "", text_pattern

    def GetRuntimeId(self):
        return list(self.rid)

    def GetValuePattern(self):
        return types.SimpleNamespace(Value=self.value)

    def GetTextPattern(self):
        return TP(self) if self.tp else None


@pytest.fixture
def ui(monkeypatch):
    state = {"ctl": Ctl("Hello world. Flowbit typed this."), "fg": 7}
    fake = types.SimpleNamespace(GetFocusedControl=lambda: state["ctl"],
                                 UIAutomationInitializerInThread=contextlib.nullcontext)
    monkeypatch.setitem(sys.modules, "uiautomation", fake)
    monkeypatch.setattr(insertion, "foreground", lambda: state["fg"])

    def send(events):  # Delete removes the current selection
        c = state["ctl"]
        c.value, c.selection = c.value.replace(c.selection, "", 1), ""
    monkeypatch.setattr(insertion, "_send", send)
    return state


def snap(state, text=" Flowbit typed this."):
    return undo.capture(text, 7)


def test_removes_exactly_the_inserted_text(ui):
    ok, msg = undo.undo(snap(ui))
    assert ok and ui["ctl"].value == "Hello world." and "Removed" in msg


def test_nothing_to_undo_and_unreadable_apps_are_refused(ui):
    assert undo.undo(None) == (False, "Nothing to undo yet.")
    s = undo.Snapshot("x", 7, None, None, 0)
    ok, msg = undo.undo(s)
    assert not ok and "own Undo" in msg


def test_refuses_when_another_window_or_box_is_focused(ui):
    s = snap(ui)
    ui["fg"] = 99
    assert not undo.undo(s)[0]
    ui["fg"] = 7
    ui["ctl"] = Ctl(ui["ctl"].value, rid=(9, 9))
    ok, msg = undo.undo(s)
    assert not ok and "different text box" in msg


def test_refuses_after_the_user_edited_the_text(ui):
    s = snap(ui)
    ui["ctl"].value += " And then I kept typing."
    ok, msg = undo.undo(s)
    assert not ok and "protect your edits" in msg and ui["ctl"].value.endswith("kept typing.")


def test_refuses_when_the_text_appears_twice(ui):
    ui["ctl"].value = "same same"
    ok, msg = undo.undo(undo.capture("same", 7))
    assert not ok and "more than once" in msg and ui["ctl"].value == "same same"


def test_refuses_without_a_text_pattern(ui):
    ui["ctl"] = Ctl("abc typed", text_pattern=False)
    ok, msg = undo.undo(undo.capture(" typed", 7))
    assert not ok and ui["ctl"].value == "abc typed"
