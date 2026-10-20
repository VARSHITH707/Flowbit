"""Smart mode end to end in the real app: hotkey -> spoken 7-point clip -> Whisper -> local AI -> pasted list,
history keeps the original, Undo AI edit restores it. Only the microphone is replaced (by the clip)."""
import ctypes
import json
import os
import re
import sys
import tempfile
import time
import wave
from pathlib import Path

home = tempfile.mkdtemp(prefix="vt_e2e_smart_")
os.environ["VOICETYPE_HOME"] = home
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
Path(home, "settings.json").write_text(json.dumps({
    "hotkeys": {"hold": "shift+f9", "toggle": "shift+f10", "cancel": "esc", "settings": "shift+f11"},
    "first_run_done": True, "model": "large-v3-turbo", "language": "en", "cleanup_mode": "smart"}), encoding="utf-8")

import numpy as np
from it_helpers import Target
from PySide6.QtWidgets import QApplication

from voicetype import insertion as ins
from voicetype.app import App

SC = {"shift": (0x2A, 0), "f9": (0x43, 0)}


def key(k, up):
    sc, ext = SC[k]
    ctypes.windll.user32.keybd_event(0, sc, 0x8 | ext | (2 if up else 0), 0)


w = wave.open(str(ROOT / "data/smart_points.wav"))
clip = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype("float32") / 32768
qapp = QApplication([])
app = App(qapp)


class FakeMic:
    def __init__(self, *a): pass
    def start(self): pass
    def stop(self): return clip
    def cancel(self): pass


app.dictation._make_recorder = FakeMic
res = []


def check(name, cond, extra=""):
    res.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name, extra)


def pump(sec):
    end = time.time() + sec
    while time.time() < end:
        qapp.processEvents()
        time.sleep(0.01)


A = Target("VT E2E Smart")
try:
    pump(8)  # hook installed + local AI warm-up
    A.focus()
    ins.set_clipboard("MY CLIPBOARD")
    key("shift", False); key("f9", False); pump(0.4)
    t0 = time.time()
    key("f9", True); key("shift", True)
    while time.time() - t0 < 60 and app.dictation.state not in ("done", "failed"):
        pump(0.05)
    sec = time.time() - t0
    pump(1.5)
    text = A.text()
    items = re.findall(r"(?m)^\s*\d+[.)]\s+(.*)$", text)
    check("dictation finished", app.dictation.state == "done", f"{app.dictation.state} in {sec:.1f}s")
    check("pasted a 7-item list", len(items) == 7, repr(text[:200]))
    check("retracted point removed, corrected point kept", "milk" not in text.lower() and "archive the old files" in text.lower())
    check("clipboard restored", ins.clipboard_snapshot()[1] == "MY CLIPBOARD")
    h = app.history.list()
    check("history keeps cleaned text and the original", len(h) == 1 and h[0].text == text and "milk" in h[0].raw.lower())
    note = app.window.home.notice.text()
    check("no AI-fallback note", "skipped" not in note.lower() and "unavailable" not in note.lower(), repr(note))
    check("Undo AI edit available", app.window.home.undo.isEnabled())
    app.window.home.undo_ai_edit()
    pump(0.5)  # Qt hands the text to the Windows clipboard asynchronously
    check("Undo AI edit puts the original on the clipboard", "milk" in (ins.clipboard_snapshot()[1] or "").lower())
finally:
    app.quit()
    A.close()
print(f"{sum(res)}/{len(res)} passed")
sys.exit(0 if all(res) else 1)
