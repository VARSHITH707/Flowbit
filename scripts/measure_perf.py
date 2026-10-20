"""7.3 / 7.4: startup, idle cost, model VRAM load/unload, key-release -> text latency, clean shutdown."""
import ctypes
import gc
import json
import os
import subprocess
import sys
import tempfile

import _projtmp  # noqa: F401  (temp files stay in the project)
import time
import wave
from pathlib import Path

import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
PY = str(ROOT / ".venv/Scripts/python.exe")
out = {}


def vram():
    return int(subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]).split()[0])


def mic_free():
    sys.path.insert(0, str(ROOT))
    from voicetype.audio import Recorder
    r = Recorder()
    r.start()
    time.sleep(0.2)
    return len(r.stop()) > 0


home = tempfile.mkdtemp(prefix="vt_perf_")
Path(home, "settings.json").write_text(json.dumps({"hotkeys": {"hold": "shift+f9", "toggle": "shift+f10", "cancel": "esc", "settings": "shift+f11"}, "first_run_done": True, "model": "large-v3-turbo"}), encoding="utf-8")
env = {**os.environ, "VOICETYPE_HOME": home}

# --- A: real app process, idle (model not loaded), then graceful exit
v0 = vram()
t0 = time.time()
p = subprocess.Popen([PY, "-m", "voicetype", "--quit-after", "18000"], env=env, cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ps = psutil.Process(p.pid)
time.sleep(4)  # let startup finish


def tree():
    return [ps] + ps.children(recursive=True)


out["process_tree"] = [q.name() for q in tree()]
out["startup_rss_mb"] = round(sum(q.memory_info().rss for q in tree()) / 2**20)
for q in tree():
    q.cpu_percent(None)
time.sleep(10)
out["idle_cpu_percent_of_all_cores"] = round(sum(q.cpu_percent(None) for q in tree()) / psutil.cpu_count(), 2)
out["idle_rss_mb"] = round(sum(q.memory_info().rss for q in tree()) / 2**20)
out["idle_threads"] = sum(q.num_threads() for q in tree())
out["vram_delta_mb_app_idle"] = vram() - v0
rc = p.wait(timeout=60)
out["app_exit_code"] = rc
out["app_total_seconds"] = round(time.time() - t0, 1)
time.sleep(1)
out["leftover_processes"] = sum(1 for q in psutil.process_iter(["pid", "cmdline"]) if q.info["cmdline"] and "voicetype" in " ".join(q.info["cmdline"]) and q.info["pid"] != os.getpid() and "-m" in q.info["cmdline"])
out["vram_after_exit_delta_mb"] = vram() - v0
out["lock_file_released"] = not Path(home, "voicetype.lock").exists()

# --- B: model VRAM load / unload (in this process)
os.environ["VOICETYPE_HOME"] = home
from voicetype.config import Config
from voicetype.transcriber import Transcriber

cfg = Config.load()
tr = Transcriber(lambda: cfg)
base = vram()
t = time.perf_counter()
tr.engine()
out["turbo_load_seconds_cached"] = round(time.perf_counter() - t, 1)
out["turbo_vram_loaded_mb"] = vram() - base
tr.unload()
gc.collect()
time.sleep(1.5)
out["turbo_vram_after_unload_mb"] = vram() - base

# --- C: latency from key release to text in the target window (real App, fake mic = TTS clip)
from it_helpers import Target
from PySide6.QtWidgets import QApplication

from voicetype.app import App

qapp = QApplication([])
app = App(qapp)
w = wave.open(str(ROOT / "data/tts_short.wav"))
clip = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype("float32") / 32768


class FakeMic:
    def __init__(self, *a): pass
    def start(self): pass
    def stop(self): return clip
    def cancel(self): pass


app.dictation._make_recorder = FakeMic
SC = {"shift": (0x2A, 0), "f9": (0x43, 0)}


def key(k, up):
    sc, ext = SC[k]
    ctypes.windll.user32.keybd_event(0, sc, 0x8 | ext | (2 if up else 0), 0)


def pump(sec):
    end = time.time() + sec
    while time.time() < end:
        qapp.processEvents()
        time.sleep(0.005)


EXPECT = "The quick brown fox jumps over the lazy dog. Please send the report to Maria by Friday afternoon."
A = Target("VT Perf Target")
lat, notes = [], []
states = []
app.bridge.state.connect(lambda st, d: states.append((st, d)))
try:
    pump(1)
    for i in range(4):  # run 0 = cold (loads the model), the rest warm
        prev = A.out.read_text(encoding="utf-8")
        focused = A.focus()
        states.clear()
        key("shift", False); key("f9", False); pump(0.3)
        t = time.perf_counter()
        key("f9", True); key("shift", True)
        ok = False
        while time.perf_counter() - t < 40:
            qapp.processEvents()
            if A.out.read_text(encoding="utf-8") == prev + EXPECT:
                ok = True
                break
            time.sleep(0.005)
        lat.append(round(time.perf_counter() - t, 2) if ok else None)
        notes.append({"run": i, "ok": ok, "focused": focused, "states": [x[0] for x in states], "detail": [x[1] for x in states if x[1]][:1]})
        pump(1.0)
    out["run_notes"] = notes
    out["latency_release_to_text_seconds_cold_then_warm"] = lat
finally:
    app.quit()
    A.close()
time.sleep(1.5)
out["vram_after_app_quit_mb_vs_base"] = vram() - base
out["mic_free_after_everything"] = mic_free()
print(json.dumps(out, indent=2))
