"""Test helpers: open Notepad, focus it, read its text back."""
import subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import win32api, win32con, win32gui, win32process

def _windows(pred):
    out = []
    win32gui.EnumWindows(lambda h, _: out.append(h) if win32gui.IsWindowVisible(h) and pred(h) else None, None)
    return out

def open_notepad():
    before = set(_windows(lambda h: win32gui.GetClassName(h) == "Notepad"))
    subprocess.Popen(["notepad.exe"])
    for _ in range(60):
        new = [h for h in _windows(lambda h: win32gui.GetClassName(h) == "Notepad") if h not in before]
        if new:
            time.sleep(1.0); return new[0]
        time.sleep(0.25)
    raise RuntimeError("Notepad window not found")

def focus(hwnd):
    win32api.keybd_event(win32con.VK_MENU, 0, 0, 0); win32api.keybd_event(win32con.VK_MENU, 0, 2, 0)  # allow SetForegroundWindow
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE); win32gui.SetForegroundWindow(hwnd); time.sleep(0.5)
    return win32gui.GetForegroundWindow() == hwnd

def edit_child(hwnd):
    kids = []
    win32gui.EnumChildWindows(hwnd, lambda h, _: kids.append(h), None)
    for h in kids:
        if "Edit" in win32gui.GetClassName(h): return h
    return None

def read_text(hwnd):
    e = edit_child(hwnd)
    if not e: return None
    n = win32gui.SendMessage(e, win32con.WM_GETTEXTLENGTH, 0, 0)
    buf = win32gui.PyMakeBuffer(2 * (n + 2))
    got = win32gui.SendMessage(e, win32con.WM_GETTEXT, n + 1, buf)
    return bytes(buf[: 2 * got]).decode("utf-16-le", "replace")

def close(hwnd):
    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0); time.sleep(0.5)
    # dismiss "save changes" dialog if shown: press Tab to "Don't save" is unreliable; kill instead
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
