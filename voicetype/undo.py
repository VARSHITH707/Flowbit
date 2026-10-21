"""Undo Last Insertion, safely.

Windows has no universal undo for text typed into another app, and blindly sending Ctrl+Z could undo something
else entirely. So Flowbit only removes its text when it can prove it is removing exactly that text:

1. The same window and the same text box (UI Automation runtime id) still have the keyboard focus.
2. The box's whole text is unchanged since the insertion (if you edited anything, nothing is touched).
3. The inserted text occurs exactly once, Flowbit selects exactly that range and checks the selection.
Only then is Delete pressed, and the result is verified. In every other case it explains why it did nothing.
Works where the app exposes its text (verified: Win11 Notepad, Edge text boxes); elsewhere it declines.
"""
import logging
import time
from dataclasses import dataclass

from . import insertion

log = logging.getLogger(__name__)
VK_DELETE = 0x2E


@dataclass(frozen=True)
class Snapshot:
    text: str  # what Flowbit inserted
    hwnd: int  # the window it went into
    rid: tuple | None  # UI Automation runtime id of the text box (None: unreadable app)
    after: str | None  # the box's full text right after inserting (None: unreadable app)
    at: float


def _norm(t: str) -> str:
    return t.replace("\r\n", "\n").replace("\r", "\n")


def capture(text: str, hwnd: int) -> Snapshot:
    """Call right after a successful paste: remembers what is needed to undo it later."""
    rid = after = None
    try:
        import uiautomation as auto
        with auto.UIAutomationInitializerInThread():
            for _ in range(10):  # slow apps show the pasted text a moment later
                c = auto.GetFocusedControl()
                v = insertion.read_control(c) if c is not None else None
                if v is not None and _norm(text) in _norm(v):
                    rid, after = tuple(c.GetRuntimeId()), v
                    break
                time.sleep(0.1)
    except Exception:
        log.info("undo snapshot unavailable")  # never log the text
    return Snapshot(text, hwnd, rid, after, time.time())


def undo(snap: Snapshot | None) -> tuple[bool, str]:
    """(done, message). Never removes anything it cannot verify."""
    if snap is None:
        return False, "Nothing to undo yet."
    if snap.after is None:
        return False, "This app does not let Flowbit read its text, so undo is not safe here. Use the app's own Undo (Ctrl+Z)."
    if insertion.foreground() != snap.hwnd:
        return False, "Click back into the window where Flowbit typed the text, then try Undo again."
    try:
        import uiautomation as auto
        with auto.UIAutomationInitializerInThread():
            return _undo_here(auto, snap)
    except Exception as e:
        log.warning("undo failed: %s", type(e).__name__)
        return False, f"Undo did not run ({type(e).__name__}); nothing was changed."


def _undo_here(auto, snap: Snapshot) -> tuple[bool, str]:
    c = auto.GetFocusedControl()
    if c is None or tuple(c.GetRuntimeId()) != snap.rid:
        return False, "The cursor is in a different text box now; click into the box Flowbit typed into and try again."
    now = insertion.read_control(c)
    if now is None or _norm(now) != _norm(snap.after):
        return False, "The text was changed after Flowbit inserted it, so Undo was skipped to protect your edits."
    if _norm(now).count(_norm(snap.text)) != 1:
        return False, "That text appears more than once in the box, so Flowbit cannot tell which one to remove."
    tp = c.GetTextPattern()
    if not tp:
        return False, "This text box cannot select text for Flowbit, so undo is not safe here. Use the app's own Undo."
    rng = None
    for variant in (snap.text, snap.text.replace("\n", "\r"), snap.text.replace("\n", "\r\n")):
        rng = tp.DocumentRange.FindText(variant, False, False)
        if rng:
            break
    if not rng:
        return False, "Flowbit could not find its text in the box; nothing was changed."
    rng.Select()
    time.sleep(0.05)
    sel = tp.GetSelection()
    if not sel or _norm(sel[0].GetText(-1)) != _norm(snap.text):
        return False, "Flowbit could not select exactly its own text; nothing was changed."
    now_focus = auto.GetFocusedControl()  # last check right before deleting: a popup may have taken focus meanwhile
    if insertion.foreground() != snap.hwnd or now_focus is None or tuple(now_focus.GetRuntimeId()) != snap.rid:
        return False, "Focus moved while undoing, so nothing was deleted."
    insertion._send([(VK_DELETE, 0, 0), (VK_DELETE, 0, insertion.KEYEVENTF_KEYUP)])
    want = _norm(now).replace(_norm(snap.text), "", 1)
    for _ in range(20):
        time.sleep(0.05)
        if _norm(insertion.read_control(c) or "") == want:
            return True, "Removed the last text Flowbit inserted."
    return False, "Delete was pressed but the result could not be confirmed; check the text and use the app's Undo if needed."
