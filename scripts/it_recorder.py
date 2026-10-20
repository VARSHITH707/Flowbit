"""Real-hardware checks 3.9, 3.10, 3.11: bad device, 20x start/stop (leaks), max duration."""
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from voicetype.audio import MicError, Recorder
from voicetype.dictation import DONE, FAILED, IDLE, Dictation, Settings
from voicetype.speech import Engine

proc = psutil.Process()
res = []


def check(name, cond, extra=""):
    res.append(cond)
    print(("PASS " if cond else "FAIL ") + name, extra)


def vram():
    return int(subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]).split()[0])


# 3.9 unavailable mic
try:
    Recorder(device=9999).start()
    check("3.9 invalid device raises MicError", False)
except MicError as e:
    check("3.9 invalid device raises MicError (no crash)", True, str(e)[:90])
r = Recorder(); r.start(); time.sleep(0.2); a = r.stop()
check("3.9 default mic works after a failed attempt", len(a) > 0, f"{len(a)} samples")

# 3.11 max duration
hit = threading.Event()
r = Recorder(max_seconds=2, on_limit=hit.set); r.start()
fired = hit.wait(5); time.sleep(0.5); a = r.stop()
check("3.11 max duration fires on_limit and caps audio", fired and len(a) <= 2 * 16000, f"fired={fired} seconds={len(a)/16000:.2f}")

# 3.10a recorder-only: 20 cycles
th0, rss0 = threading.active_count(), proc.memory_info().rss / 2**20
ok = True
for i in range(20):
    r = Recorder()
    try:
        r.start(); time.sleep(0.25); a = r.stop()
        ok &= len(a) > 0 and not r.recording
    except Exception as e:
        ok = False; print("  cycle", i, "error", e)
time.sleep(0.5)
th1, rss1 = threading.active_count(), proc.memory_info().rss / 2**20
check("3.10a recorder 20x: all cycles recorded, stream closed", ok)
check("3.10a recorder 20x: no thread growth, RAM growth < 20 MB", th1 <= th0 + 1 and rss1 - rss0 < 20, f"threads {th0}->{th1}, RAM {rss0:.0f}->{rss1:.0f} MB")

# 3.10b full pipeline: 20 start/stop with the real model (mic is whatever the room gives; errors for silence are expected and fine)
engine = Engine("small")
import wave as _wave
_w = _wave.open(str(Path(__file__).resolve().parents[1] / "data/tts_short.wav"))
engine.transcribe(np.frombuffer(_w.readframes(_w.getnframes()), "<i2").astype("float32") / 32768, language="en")  # warm-up: first real decode allocates ~0.5 GB once
outcomes, done = [], threading.Event()


def on_state(s, d=""):
    if s in (DONE, FAILED, IDLE) and s != "idle":
        outcomes.append((s, d)); done.set()


dic = Dictation(lambda: engine, Settings(auto_insert=False), on_state=on_state)
v0, rss0, th0 = vram(), proc.memory_info().rss / 2**20, threading.active_count()
for i in range(20):
    done.clear(); dic.start(); time.sleep(0.8); dic.stop()
    if not done.wait(30):
        print("  cycle", i, "timed out")
    time.sleep(0.1)
time.sleep(1)
v1, rss1, th1 = vram(), proc.memory_info().rss / 2**20, threading.active_count()
check("3.10b pipeline 20x: every cycle ended in done/failed", len(outcomes) == 20, f"{len(outcomes)} outcomes; done={sum(o[0]==DONE for o in outcomes)} failed={sum(o[0]==FAILED for o in outcomes)}")
check("3.10b pipeline 20x: VRAM drift < 50 MB, RAM drift < 100 MB, no thread growth", v1 - v0 < 50 and rss1 - rss0 < 100 and th1 <= th0 + 2,
      f"VRAM {v0}->{v1} MB, RAM {rss0:.0f}->{rss1:.0f} MB, threads {th0}->{th1}")
r = Recorder(); r.start(); time.sleep(0.2); a = r.stop()
check("3.10b mic still free afterwards", len(a) > 0)
print(f"{sum(res)}/{len(res)} passed")
sys.exit(0 if all(res) else 1)
