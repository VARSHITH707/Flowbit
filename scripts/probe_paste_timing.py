"""How long after Ctrl+V does pasted text actually appear in Win11 Notepad? (diagnosis for intermittent paste misses)"""
import subprocess
import sys
import tempfile

import _projtmp  # noqa: F401  (temp files stay in the project)
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uiautomation as auto
import win32con
import win32gui

from it_learn_helpers import close_own_tab  # noqa: E402
from voicetype import insertion as ins
from voicetype.learner import _read


def notepads():
    out = []
    win32gui.EnumWindows(lambda h, _: out.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "Notepad" else None, None)
    return set(out)


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
        time.sleep(0.5)
        if win32gui.GetForegroundWindow() == hwnd:
            return True
    return False


if notepads():
    sys.exit("Notepad already open; not touching it")
path = Path(tempfile.gettempdir()) / "vt_paste_probe.txt"
path.write_text("", encoding="utf-8")
subprocess.Popen(["notepad.exe", str(path)])
hwnd = None
for _ in range(60):
    n = notepads()
    if n and "vt_paste_probe" in win32gui.GetWindowText(next(iter(n))):
        hwnd = next(iter(n)); break
    time.sleep(0.25)
time.sleep(1)
CTRL_V = [(0x11, 0, 0), (0x56, 0, 0), (0x56, 0, 2), (0x11, 0, 2)]
with auto.UIAutomationInitializerInThread():
    try:
        focus(hwnd)
        ctrl = auto.GetFocusedControl()
        for i, n in enumerate([60, 600, 1800] * 4):
            marker = f"[{i}]" + ("x" * n)
            ins.set_clipboard(marker)
            t0 = time.perf_counter()
            ins._send(CTRL_V)
            seen = None
            while time.perf_counter() - t0 < 4:
                v = _read(ctrl) or ""
                if marker in v:
                    seen = time.perf_counter() - t0
                    break
                time.sleep(0.01)
            print(f"paste {i:2d}: {n:5d} chars -> {'appeared after %.3f s' % seen if seen is not None else 'NOT seen within 4 s'}")
            ins._send([(0x11, 0, 0), (0x41, 0, 0), (0x41, 0, 2), (0x11, 0, 2), (0x2E, 0, 0), (0x2E, 0, 2)])  # clear: Ctrl+A, Del
            time.sleep(0.3)
    finally:
        ins._send([(0x11, 0, 0), (0x53, 0, 0), (0x53, 0, 2), (0x11, 0, 2)])
        time.sleep(0.8)
        close_own_tab(hwnd, path.name)  # never the whole window: it may hold the user's restored tabs
        time.sleep(1)
        if hwnd not in notepads():
            path.unlink(missing_ok=True)
