"""Can we read the focused text box of other apps via UI Automation? (feasibility probe for auto-learn)"""
import subprocess
import sys
import tempfile

import _projtmp  # noqa: F401  (temp files stay in the project)
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import uiautomation as auto
import win32con
import win32gui

from it_helpers import Target
from voicetype import insertion as ins


def read_focused():
    c = auto.GetFocusedControl()
    if c is None:
        return None, "no focused control"
    for how in ("value", "text"):
        try:
            if how == "value":
                p = c.GetValuePattern()
                if p:
                    return p.Value, f"ValuePattern on {c.ControlTypeName}"
            else:
                p = c.GetTextPattern()
                if p:
                    return p.DocumentRange.GetText(-1), f"TextPattern on {c.ControlTypeName}"
        except Exception as e:
            last = e
    return None, f"no readable pattern on {c.ControlTypeName} ({c.ClassName})"


def focus(hwnd):
    import win32api
    import win32process
    for _ in range(6):
        me = win32api.GetCurrentThreadId()
        fg = win32gui.GetForegroundWindow()
        ft = win32process.GetWindowThreadProcessId(fg)[0] if fg else me
        win32process.AttachThreadInput(me, ft, True)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        finally:
            win32process.AttachThreadInput(me, ft, False)
        time.sleep(0.6)
        if win32gui.GetForegroundWindow() == hwnd:
            return True
    return False


with auto.UIAutomationInitializerInThread():
    # Tk window we own
    A = Target("VT UIA Probe")
    try:
        A.focus(); ins.insert("hello from voicetype tk", A.hwnd); time.sleep(0.5)
        print("Tk     :", read_focused())
    finally:
        A.close()

    # real Notepad (temp file, only our own window, saved before close)
    def notepads():
        out = []
        win32gui.EnumWindows(lambda h, _: out.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "Notepad" else None, None)
        return set(out)
    if notepads():
        print("Notepad: skipped (a Notepad window is already open)")
    else:
        path = Path(tempfile.gettempdir()) / "vt_uia_probe.txt"
        path.write_text("", encoding="utf-8")
        subprocess.Popen(["notepad.exe", str(path)])
        hwnd = None
        for _ in range(60):
            n = notepads()
            if n and "vt_uia_probe" in win32gui.GetWindowText(next(iter(n))):
                hwnd = next(iter(n)); break
            time.sleep(0.25)
        time.sleep(1); focus(hwnd)
        ins.insert("hello from voicetype notepad", hwnd); time.sleep(0.6)
        print("Notepad:", read_focused())
        ins._send([(0x11, 0, 0), (0x53, 0, 0), (0x53, 0, 2), (0x11, 0, 2)]); time.sleep(0.8)
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0); time.sleep(1)
        path.unlink(missing_ok=True)

    # Edge textarea, isolated profile
    exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    work = Path(tempfile.mkdtemp(prefix="vt_uia_edge_"))
    page = work / "p.html"
    page.write_text("<!doctype html><title>VT UIA Edge</title><textarea autofocus rows=5 cols=50></textarea>", encoding="utf-8")
    before = set()
    win32gui.EnumWindows(lambda h, _: before.add(h), None)
    p = subprocess.Popen([exe, f"--user-data-dir={work / 'prof'}", "--no-first-run", "--new-window", page.as_uri()])
    hwnd = None
    for _ in range(80):
        found = []
        win32gui.EnumWindows(lambda h, _: found.append(h) if h not in before and win32gui.GetWindowText(h).startswith("VT UIA Edge") else None, None)
        if found:
            hwnd = found[0]; break
        time.sleep(0.25)
    time.sleep(1.5); focus(hwnd)
    ins.insert("hello from voicetype edge", hwnd); time.sleep(0.6)
    print("Edge   :", read_focused())
    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
