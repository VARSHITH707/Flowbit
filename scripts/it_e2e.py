"""End-to-end on the real desktop: hotkey -> (fake mic = known TTS clip) -> real GPU transcription -> insert -> history.
Only the microphone is replaced; everything else is the real App."""
import ctypes
import json
import os
import sys
import tempfile

import _projtmp  # noqa: F401  (temp files stay in the project)
import time
import wave
from pathlib import Path

home = tempfile.mkdtemp(prefix="vt_e2e_home_")
os.environ["VOICETYPE_HOME"] = home
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
Path(home, "settings.json").write_text(json.dumps({"hotkeys": {"hold": "shift+f9", "toggle": "shift+f10", "cancel": "esc", "settings": "shift+f11"}, "first_run_done": True, "model": "small", "language": "en", "unload_minutes": 0}), encoding="utf-8")

import numpy as np
from it_helpers import Target
from PySide6.QtWidgets import QApplication

from voicetype import insertion as ins
from voicetype.app import App

SC = {"ctrl": (0x1D, 0), "windows": (0x5B, 1), "alt": (0x38, 0), "space": (0x39, 0), "esc": (0x01, 0), "d": (0x20, 0), "shift": (0x2A, 0), "f9": (0x43, 0), "f10": (0x44, 0), "f11": (0x57, 0)}


def key(k, up):
    sc, ext = SC[k]
    ctypes.windll.user32.keybd_event(0, sc, 0x8 | ext | (2 if up else 0), 0)


def load(name):
    w = wave.open(str(ROOT / f"data/tts_{name}.wav"))
    return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype("float32") / 32768


qapp = QApplication(sys.argv[:1])
app = App(qapp)
clip = {"audio": load("short")}


class FakeMic:
    def __init__(self, *a): pass
    def start(self): pass
    def stop(self): return clip["audio"]
    def cancel(self): pass


app.dictation._make_recorder = FakeMic
ST = []
app.bridge.state.connect(lambda st, d: ST.append((st, d[:80])))
res = []


def check(name, cond, extra=""):
    res.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name, extra)


def pump(sec):
    end = time.time() + sec
    while time.time() < end:
        qapp.processEvents()
        time.sleep(0.01)


def wait_state(*states, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        qapp.processEvents()
        if app.dictation.state in states:
            return True
        time.sleep(0.01)
    return False


EXPECT = "The quick brown fox jumps over the lazy dog. Please send the report to Maria by Friday afternoon."
A, B = Target("VT E2E A"), Target("VT E2E B")
try:
    pump(1.0)  # hook installed
    # 1. hold-to-talk end to end
    A.focus(); ins.set_clipboard("MY CLIPBOARD")
    key("shift", False); key("f9", False); pump(0.4)
    check("hold: state is recording while keys held", app.dictation.state == "recording")
    key("f9", True); key("shift", True)
    ok = wait_state("done", "failed")
    pump(1.5)
    import win32gui
    fgw = win32gui.GetForegroundWindow()
    check("hold: dictation finished DONE", ok and app.dictation.state == "done", f"{app.dictation.state} | states={[x for x in ST]} | foreground now={win32gui.GetWindowText(fgw)!r}/{win32gui.GetClassName(fgw)!r}")
    check("hold: exact text inserted into the focused app", A.text() == EXPECT, repr(A.text()))
    check("hold: clipboard restored", ins.clipboard_snapshot()[1] == "MY CLIPBOARD")
    h = app.history.list()
    check("history row saved", len(h) == 1 and h[0].text == EXPECT)
    log = Path(home, "voicetype.log")
    logtxt = log.read_text(encoding="utf-8") if log.exists() else ""
    check("4.12 log never contains transcript text", "quick brown fox" not in logtxt and "Maria" not in logtxt, f"log={len(logtxt)} bytes")

    # 2. toggle hotkey
    A.focus(); before = A.text()
    key("shift", False); key("f10", False); key("f10", True); key("shift", True)
    pump(0.4)
    check("toggle: first press starts recording", app.dictation.state == "recording")
    key("shift", False); key("f10", False); key("f10", True); key("shift", True)
    ok = wait_state("done", "failed"); pump(1.5)
    check("toggle: second press stops and inserts", ok and A.text() == before + EXPECT, repr(A.text()[len(before):][:60]))

    # 3. cancel during processing (long clip so processing lasts several seconds)
    clip["audio"] = load("long")
    A.focus(); before = A.text()
    key("shift", False); key("f9", False); pump(0.3); key("f9", True); key("shift", True)
    pump(1.0)
    check("cancel: processing started", app.dictation.state == "processing")
    key("esc", False); key("esc", True); pump(0.5)
    check("cancel: esc returns to idle", app.dictation.state == "idle", app.dictation.state)
    pump(14)  # let the abandoned transcription finish in the background
    check("cancel: nothing was inserted", A.text() == before and app.dictation.state == "idle", f"state={app.dictation.state}")

    # 4. focus changes during recording -> never typed into the wrong window
    clip["audio"] = load("short")
    A.focus(); a0, b0 = A.text(), B.text()
    key("shift", False); key("f9", False); pump(0.4)
    B.focus(); pump(0.3)
    key("f9", True); key("shift", True)
    ok = wait_state("done", "failed"); pump(1.0)
    _, clipboard = ins.clipboard_snapshot()
    check("focus moved: text NOT typed into A or B", A.text() == a0 and B.text() == b0, f"A+={len(A.text())-len(a0)} B+={len(B.text())-len(b0)}")
    check("focus moved: text copied to clipboard instead", clipboard == EXPECT, repr(clipboard)[:50])
finally:
    app.quit()
    A.close()
    B.close()
print(f"{sum(res)}/{len(res)} passed")
sys.exit(0 if all(res) else 1)
