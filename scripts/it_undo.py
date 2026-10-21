"""Undo Last Insertion for real: Notepad and an Edge text box (own windows, temp file, isolated browser profile).
Checks it removes exactly Flowbit's text, and refuses (changing nothing) after an edit, in another window, or in an
app whose text it cannot read."""
import os
import subprocess
import sys
import tempfile

import _projtmp  # noqa: F401  (temp files stay in the project)
import time
from pathlib import Path

os.environ["VOICETYPE_HOME"] = tempfile.mkdtemp(prefix="vt_undo_")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import win32con
import win32gui

from it_helpers import Target
from it_learn_helpers import SELECT_ALL, close_own_tab, focus, focus_editor, notepads, read_box
from voicetype import insertion as ins
from voicetype import undo

res = []


def check(name, cond, extra=""):
    res.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name, extra)


def scenario(label: str, hwnd: int, away: Target) -> None:
    focus(hwnd)
    focus_editor(hwnd)
    ins._send(SELECT_ALL)
    time.sleep(0.2)
    ins.type_text("Before.")
    time.sleep(0.5)
    text = " Flowbit inserted this line."
    check(f"{label}: inserted", ins.insert(text, hwnd).status == "inserted")
    snap = undo.capture(text, hwnd)
    ok, msg = undo.undo(snap)
    time.sleep(0.3)
    check(f"{label}: undo removes exactly the inserted text", ok and read_box() == "Before.", f"{msg} | {read_box()!r}")

    check(f"{label}: inserted again", ins.insert(text, hwnd).status == "inserted")
    snap = undo.capture(text, hwnd)
    ins.type_text(" Then I kept typing.")
    time.sleep(0.5)
    ok, msg = undo.undo(snap)
    check(f"{label}: after an edit, undo refuses and changes nothing",
          not ok and read_box().endswith("Then I kept typing.") and text in read_box(), msg)

    ins._send(SELECT_ALL)
    time.sleep(0.2)
    ins.type_text("Start.")
    time.sleep(0.4)
    ins.insert(text, hwnd)
    snap = undo.capture(text, hwnd)
    away.focus()
    ok, msg = undo.undo(snap)
    focus(hwnd)
    focus_editor(hwnd)
    check(f"{label}: with another window in front, undo refuses", not ok and text in read_box(), msg)


away = Target("VT Undo Away")
try:
    if notepads():
        print("SKIP Notepad: a Notepad window is already open (never touched)")
    else:
        path = Path(tempfile.gettempdir()) / "vt_undo_test.txt"
        path.write_text("", encoding="utf-8")
        subprocess.Popen(["notepad.exe", str(path)])
        np_hwnd = None
        for _ in range(60):
            n = notepads()
            if n and "vt_undo_test" in win32gui.GetWindowText(next(iter(n))):
                np_hwnd = next(iter(n))
                break
            time.sleep(0.25)
        time.sleep(1)
        scenario("Notepad", np_hwnd, away)
        focus(np_hwnd)
        ins._send([(0x11, 0, 0), (0x53, 0, 0), (0x53, 0, 2), (0x11, 0, 2)])  # Ctrl+S: our own temp file
        time.sleep(0.8)
        close_own_tab(np_hwnd, path.name)  # never the whole window: it may hold the user's restored tabs
        time.sleep(1)
        path.unlink(missing_ok=True)

    exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    work = Path(tempfile.mkdtemp(prefix="vt_undo_edge_"))
    page = work / "p.html"
    page.write_text("<!doctype html><title>VT Undo Edge</title><textarea autofocus rows=5 cols=50></textarea>", encoding="utf-8")
    before = set()
    win32gui.EnumWindows(lambda h, _: before.add(h), None)
    subprocess.Popen([exe, f"--user-data-dir={work / 'prof'}", "--no-first-run", "--no-default-browser-check", "--inprivate", "--new-window", page.as_uri()])
    ed = None
    for _ in range(80):
        found = []
        win32gui.EnumWindows(lambda h, _: found.append(h) if h not in before and win32gui.GetWindowText(h).startswith("VT Undo Edge") else None, None)
        if found:
            ed = found[0]
            break
        time.sleep(0.25)
    time.sleep(1.5)
    scenario("Edge", ed, away)
    win32gui.PostMessage(ed, win32con.WM_CLOSE, 0, 0)

    away.focus()
    ins.insert(" tk text", away.hwnd)
    snap = undo.capture(" tk text", away.hwnd)
    ok, msg = undo.undo(snap)
    check("App that hides its text (Tk): undo declines and explains", not ok and "own Undo" in msg and away.text().endswith(" tk text"), msg)
finally:
    away.close()
print(f"{sum(res)}/{len(res)} passed")
sys.exit(0 if all(res) else 1)
