"""Auto-learn for real: VoiceType pastes into Notepad / Edge, the 'user' fixes a word, focus leaves, memory learns.
Same safeguards as the other scripts: temp file, own windows only, isolated browser profile, temp data folder."""
import os
import subprocess
import sys
import tempfile

import _projtmp  # noqa: F401  (temp files stay in the project)
import time
from pathlib import Path

os.environ["VOICETYPE_HOME"] = tempfile.mkdtemp(prefix="vt_learn_")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import win32con
import win32gui

from it_helpers import Target
from it_learn_helpers import close_own_tab  # noqa: E402
from voicetype import insertion as ins
from voicetype import memory
from voicetype.learner import EditWatcher

res = []


def check(name, cond, extra=""):
    res.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name, extra)


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


def focus_editor(hwnd):
    import uiautomation as auto
    with auto.UIAutomationInitializerInThread():
        root = auto.ControlFromHandle(hwnd)
        box = root.DocumentControl(searchDepth=12)
        if not box.Exists(1):
            box = root.EditControl(searchDepth=25)
        if box.Exists(3):
            box.SetFocus()
    time.sleep(0.3)


SELECT_ALL = [(0x11, 0, 0), (0x41, 0, 0), (0x41, 0, 2), (0x11, 0, 2)]


def round_trip(hwnd, away: Target, inserted: str, user_fix: str) -> list:
    """Paste `inserted`, let the 'user' replace it with `user_fix`, leave the box, return what was learned."""
    learned = []
    focus(hwnd)
    focus_editor(hwnd)
    ins._send(SELECT_ALL)
    time.sleep(0.2)
    assert ins.insert(inserted, hwnd).status == "inserted"
    w = EditWatcher(on_learned=learned.extend, seconds=30, poll=0.5)
    w.watch(inserted, cleaned=inserted)
    time.sleep(1.5)
    ins._send(SELECT_ALL)
    time.sleep(0.2)
    ins.type_text(user_fix)  # the user's correction, typed in the app
    time.sleep(1.5)
    away.focus()  # user moves on
    end = time.time() + 8
    while time.time() < end and w._thread.is_alive():
        time.sleep(0.2)
    print("   trace:", w.trace)
    return learned


away = Target("VT Learn Away")
try:
    # ---------------- Notepad
    def notepads():
        out = []
        win32gui.EnumWindows(lambda h, _: out.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "Notepad" else None, None)
        return set(out)

    if notepads():
        print("SKIP Notepad: a Notepad window is already open")
    else:
        path = Path(tempfile.gettempdir()) / "vt_learn_test.txt"
        path.write_text("", encoding="utf-8")
        subprocess.Popen(["notepad.exe", str(path)])
        np_hwnd = None
        for _ in range(60):
            n = notepads()
            if n and "vt_learn_test" in win32gui.GetWindowText(next(iter(n))):
                np_hwnd = next(iter(n)); break
            time.sleep(0.25)
        time.sleep(1)
        got = round_trip(np_hwnd, away, "We deploy on cubernetes today.", "We deploy on Kubernetes today.")
        check("Notepad: learned the name fix", ("cubernetes", "Kubernetes") in got, repr(got))
        check("Notepad: name fix is active immediately", "cubernetes=>Kubernetes" in memory.vocab_entries())
        got = round_trip(np_hwnd, away, "Please send the file.", "Please sent the file.")
        check("Notepad: ordinary word fix recorded", any(d["heard"] == "send" for d in memory.learned()), repr(got))
        check("Notepad: ordinary word fix NOT active after one edit", "send=>sent" not in memory.vocab_entries())
        round_trip(np_hwnd, away, "Please send the file.", "Please sent the file.")
        check("Notepad: same fix twice -> active", "send=>sent" in memory.vocab_entries())
        got = round_trip(np_hwnd, away, "The launch is on Friday.", "The launch is on Monday.")
        check("Notepad: content change (Friday -> Monday) is NOT learned", not any(d["heard"] == "Friday" for d in memory.learned()), repr(got))
        focus(np_hwnd)
        ins._send([(0x11, 0, 0), (0x53, 0, 0), (0x53, 0, 2), (0x11, 0, 2)])
        time.sleep(0.8)
        close_own_tab(np_hwnd, path.name)  # never the whole window: it may hold the user's restored tabs
        time.sleep(1)
        path.unlink(missing_ok=True)

    # ---------------- Edge textarea (isolated profile)
    exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    work = Path(tempfile.mkdtemp(prefix="vt_learn_edge_"))
    page = work / "p.html"
    page.write_text("<!doctype html><title>VT Learn Edge</title><textarea autofocus rows=5 cols=50></textarea>", encoding="utf-8")
    before = set()
    win32gui.EnumWindows(lambda h, _: before.add(h), None)
    subprocess.Popen([exe, f"--user-data-dir={work / 'prof'}", "--no-first-run", "--no-default-browser-check", "--inprivate", "--new-window", page.as_uri()])
    ed = None
    for _ in range(80):
        found = []
        win32gui.EnumWindows(lambda h, _: found.append(h) if h not in before and win32gui.GetWindowText(h).startswith("VT Learn Edge") else None, None)
        if found:
            ed = found[0]; break
        time.sleep(0.25)
    time.sleep(1.5)
    got = round_trip(ed, away, "Point it at post gress please.", "Point it at Postgres please.")
    check("Edge: learned a multi-word mis-hearing", ("post gress", "Postgres") in got, repr(got))
    check("Edge: active", "post gress=>Postgres" in memory.vocab_entries())
    win32gui.PostMessage(ed, win32con.WM_CLOSE, 0, 0)

    # ---------------- an app that does not expose its text: nothing learned, nothing breaks
    learned = []
    away.focus()
    ins.insert("tk has no ui automation text", away.hwnd)
    w = EditWatcher(on_learned=learned.extend, seconds=3, poll=0.5)
    w.watch("tk has no ui automation text")
    time.sleep(4)
    check("Unsupported app: watcher gives up quietly", learned == [] and not w._thread.is_alive())
    print("memory folder:", sorted(p.name for p in memory.memory_dir().iterdir()))
finally:
    away.close()
print(f"{sum(res)}/{len(res)} passed")
sys.exit(0 if all(res) else 1)
