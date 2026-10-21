"""Real desktop: the Flowbit mascot never takes focus, reacts to a real mouse click and drag; the UI stays
responsive while transcribing (4.2)."""
import os
import sys
import tempfile

import _projtmp  # noqa: F401  (temp files stay in the project)
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
from voicetype.ui.mascot import Mascot

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
    import win32api
    import win32con
    import win32gui
    from PySide6.QtCore import QPoint
    check("test window has the keyboard focus before the mascot appears", A.focus() and ins.foreground() == A.hwnd)
    m = Mascot()
    m.configure(True, 0.9, False, None)
    clicks, moves = [], []
    m.clicked.connect(lambda: clicks.append(1))
    m.moved.connect(lambda x, y: moves.append((x, y)))
    seen = []
    for st, det in [("idle", ""), ("recording", ""), ("processing", ""), ("inserting", ""), ("done", ""),
                    ("failed", "Microphone unavailable: test"), ("idle", "")]:
        m.set_state(st, det, "toggle")
        pump(0.3)
        seen.append(ins.foreground() == A.hwnd)
    check("mascot shown in all 6 states, foreground never changed", all(seen), str(seen))
    ex = win32gui.GetWindowLong(int(m.winId()), -20)
    check("mascot window: NOACTIVATE + TOOLWINDOW, and NOT click-through", m.isVisible() and (ex & 0x08000000) and (ex & 0x80) and not (ex & 0x20), hex(ex))

    def mascot_center():  # physical pixels (works with display scaling)
        l, t, r, b = win32gui.GetWindowRect(int(m.winId()))
        dpr = (r - l) / m.width()
        return int(l + (m._mascot_x() + 30) * dpr), int(t + 30 * dpr)
    old_cursor = win32api.GetCursorPos()
    try:
        x, y = mascot_center()
        win32api.SetCursorPos((x, y))
        pump(0.15)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        pump(0.08)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
        pump(0.4)
        check("real mouse click on the mascot emits 'clicked' (start/stop recording)", clicks == [1], str(clicks))
        check("clicking the mascot did not take focus from the app being typed in", ins.foreground() == A.hwnd)
        before = win32gui.GetWindowRect(int(m.winId()))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        for i in range(1, 13):
            win32api.SetCursorPos((x - 8 * i, y - 4 * i))
            pump(0.03)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
        pump(0.4)
        after = win32gui.GetWindowRect(int(m.winId()))
        check("real mouse drag moves the mascot and reports the new position", len(moves) == 1 and after[:2] != before[:2],
              f"{before[:2]} -> {after[:2]}, moves={moves}")
        check("a drag is not counted as a click", clicks == [1])
        check("dragging did not take focus either", ins.foreground() == A.hwnd)
    finally:
        win32api.SetCursorPos(old_cursor)
    ins.insert("still typing here", A.hwnd, "type")
    check("typing still reaches the target while the mascot is visible", "still typing here" in A.text())
    m.hide()

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
