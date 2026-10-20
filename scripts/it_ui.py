"""Checks 4.2 and 4.4 on the real desktop: pill never takes focus; UI event loop stays responsive while transcribing."""
import os
import sys
import tempfile
import time
import wave
from pathlib import Path

os.environ["VOICETYPE_HOME"] = tempfile.mkdtemp(prefix="vt_ui_home_")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from it_helpers import Target
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from voicetype import insertion as ins
from voicetype.config import Config
from voicetype.dictation import DONE, FAILED, Dictation, Settings
from voicetype.transcriber import Transcriber
from voicetype.ui.pill import StatePill

app = QApplication(sys.argv[:1])
res = []


def check(name, cond, extra=""):
    res.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name, extra)


def pump(sec):
    end = time.time() + sec
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


A = Target("VT UI Target")
try:
    A.focus()
    pill = StatePill()
    seen = []
    for st, det in [("idle", ""), ("recording", ""), ("processing", ""), ("done", ""), ("failed", "Microphone unavailable: test"), ("idle", "")]:
        pill.set_state(st, det)
        pump(0.3)
        seen.append(ins.foreground() == A.hwnd)
    check("4.4 pill shown in all 5 states, foreground never changed", all(seen), str(seen))
    import win32gui
    ex = win32gui.GetWindowLong(int(pill.winId()), -20)
    check("4.4 pill window has WS_EX_NOACTIVATE + TOOLWINDOW + TRANSPARENT", pill.isVisible() and (ex & 0x08000000) and (ex & 0x80) and (ex & 0x20), hex(ex))
    ins.insert("still typing here", A.hwnd, "type")
    check("4.4 typing still reaches the target while pill is visible", "still typing here" in A.text())

    # 4.2 responsiveness: real worker thread, real model, 5.7 min clip
    cfg = Config.load()
    cfg.model = "small"
    w = wave.open(str(Path(__file__).resolve().parents[1] / "data/tts_long.wav"))
    audio = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype("float32") / 32768

    class Rec:
        def __init__(self, *a): pass
        def start(self): pass
        def stop(self): return audio
        def cancel(self): pass

    tr = Transcriber(lambda: cfg)
    tr.engine()  # load first so we measure transcription, not load
    outcome = {}
    d = Dictation(lambda: tr, Settings(auto_insert=False, language="en"), on_state=lambda s, det="": outcome.__setitem__("s", s),
                  on_result=lambda res, r: outcome.__setitem__("text", res.text), recorder_factory=Rec, foreground=lambda: 1)
    gaps, last = [], [time.perf_counter()]

    def tick():
        now = time.perf_counter()
        gaps.append(now - last[0])
        last[0] = now
    t = QTimer(interval=20, timeout=tick)
    t.start()
    d.start(); d.stop()
    t0 = time.time()
    while outcome.get("s") not in (DONE, FAILED) and time.time() - t0 < 120:
        app.processEvents()
        time.sleep(0.005)
    el = time.time() - t0
    t.stop()
    mx = max(gaps)
    check("4.2 long transcription completed", outcome.get("s") == DONE and len(outcome.get("text", "")) > 1000, f"{el:.1f}s, {len(outcome.get('text',''))} chars")
    check("4.2 UI event loop max stall < 250 ms during transcription", mx < 0.25, f"max gap {mx*1000:.0f} ms over {len(gaps)} ticks")
finally:
    A.close()
print(f"{sum(res)}/{len(res)} passed")
sys.exit(0 if all(res) else 1)
