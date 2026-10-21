"""Check 3.3 in real Win11 Notepad. Safeguards: temp file, only the window we create, no process kills.
Read-back is from the saved file: Notepad's WinUI edit control is unreliable through WM_GETTEXT."""
import subprocess
import sys
import tempfile

import _projtmp  # noqa: F401  (temp files stay in the project)
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import win32api
import win32gui
import win32process

from it_learn_helpers import close_own_tab  # noqa: E402
from voicetype import insertion as ins

path = Path(tempfile.gettempdir()) / "vt_np_test.txt"
CTRL_S = [(0x11, 0, 0), (0x53, 0, 0), (0x53, 0, 2), (0x11, 0, 2)]


def notepads():
    out = []
    win32gui.EnumWindows(lambda h, _: out.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "Notepad" else None, None)
    return set(out)


def focus(hwnd):
    for _ in range(6):  # Windows can refuse SetForegroundWindow right after another focus change
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
        time.sleep(0.8)
        if win32gui.GetForegroundWindow() == hwnd:
            return True
    return False



def focus_editor(hwnd):
    """Win11 Notepad sometimes opens with keyboard focus on a toolbar button; put the cursor in the text area."""
    import uiautomation as auto
    with auto.UIAutomationInitializerInThread():
        doc = auto.ControlFromHandle(hwnd).DocumentControl(searchDepth=12)
        if doc.Exists(3):
            doc.SetFocus()
    time.sleep(0.3)


def saved_text():
    """Read Notepad's text via UI Automation: no extra keystrokes that could disturb the test."""
    import uiautomation as auto
    time.sleep(0.6)
    with auto.UIAutomationInitializerInThread():
        c = auto.GetFocusedControl()
        v = ins.read_control(c) if c is not None else None
    return "\n".join((v or "").splitlines())


path.write_text("", encoding="utf-8")
before = notepads()
if before:
    sys.exit(f"Refusing to run: Notepad already open ({before}); would risk touching your session.")
subprocess.Popen(["notepad.exe", str(path)])
hwnd = None
for _ in range(80):
    new = notepads() - before
    if new:
        hwnd = next(iter(new))
        if "vt_np_test" in win32gui.GetWindowText(hwnd):
            break
    time.sleep(0.25)
else:
    sys.exit("Notepad window with the test file not found; nothing was changed.")
time.sleep(1.0)
res = []


def check(name, cond, extra=""):
    res.append(cond)
    print(("PASS " if cond else "FAIL ") + name, extra)


try:
    check("focus Notepad", focus(hwnd))
    import uiautomation as auto
    with auto.UIAutomationInitializerInThread():  # real-world guard: a focused BUTTON must not swallow the dictation
        btn = auto.ControlFromHandle(hwnd).ButtonControl(searchDepth=12)
        btn_ok = btn.Exists(3) and btn.SetFocus()
    if btn_ok:
        r = ins.insert("should not vanish", ins.foreground())
        check("button focused -> text copied with a message, not lost", r.status == "copied" and "No text box" in r.detail
              and ins.clipboard_snapshot()[1] == "should not vanish", r.detail[:60])
    focus_editor(hwnd)
    target = ins.foreground()
    r = ins.insert("Hello from VoiceType.", target, "type")  # typing fallback, ASCII
    got = saved_text()
    check("single-line TYPED (paced) into Notepad", r.status == "inserted" and got == "Hello from VoiceType.", repr(got))
    uni = " héllo wörld — 日本語 😀"
    r = ins.insert(uni, target)  # default path (paste): the reliable one for accents/emoji
    got = saved_text()
    check("unicode+emoji via default path into Notepad", r.status == "inserted" and got == "Hello from VoiceType." + uni, f"status={r.status} {r.detail[:50]} | {got!r}")
    ins.set_clipboard("USER CLIPBOARD")
    ml = "\nline two\n\nnew paragraph"
    r = ins.insert(ml, target)
    time.sleep(0.5)
    got = saved_text()
    check("multiline via default (auto -> paste) into Notepad", r.status == "inserted" and got == "Hello from VoiceType." + uni + ml, f"status={r.status} {r.detail[:50]} | {got!r}")
    check("clipboard preserved", ins.clipboard_snapshot()[1] == "USER CLIPBOARD")
    longtxt = " " + ("The quick brown fox jumps over the lazy dog. " * 40).strip()
    r = ins.insert(longtxt, target)
    time.sleep(0.5)
    got = saved_text()
    check("long single-line (%d chars) default path" % len(longtxt), r.status == "inserted" and got.endswith(longtxt), f"status={r.status} {r.detail[:60]} | {got[-40:]!r}")
    r = ins.insert(" typed-after", target, "type")
    got = saved_text()
    check("typing again after paste still works", got.endswith(longtxt + " typed-after"), repr(got[-30:]))
finally:
    ins._send(CTRL_S)  # save once so closing shows no prompt
    time.sleep(0.8)
    close_own_tab(hwnd, path.name)  # never the whole window: it may hold the user's restored tabs
    time.sleep(1.0)
    closed = hwnd not in notepads()
    print("our Notepad window closed:", closed)
    if closed:
        path.unlink(missing_ok=True)
print(f"{sum(res)}/{len(res)} passed")
sys.exit(0 if all(res) else 1)
