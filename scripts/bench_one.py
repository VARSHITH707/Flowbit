"""Benchmark one model: python scripts/bench_one.py <model> [device]. Prints a JSON line."""
import json, re, subprocess, sys, time, wave
from pathlib import Path
import numpy as np, psutil
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from voicetype.speech import Engine

def load(p):
    w = wave.open(p); return np.frombuffer(w.readframes(w.getnframes()), '<i2').astype('float32') / 32768

def words(t): return re.findall(r"[a-z0-9']+", t.lower())

def wer(ref, hyp):
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)] / max(len(r), 1)

def vram():
    o = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"])
    return int(o.split()[0])

model = sys.argv[1]; dev = sys.argv[2] if len(sys.argv) > 2 else "auto"
v0 = vram(); proc = psutil.Process()
e = Engine(model, device=dev)
out = {"model": model, "device": e.device, "load_s": round(e.load_seconds, 1)}
for name in ("short", "long"):
    audio = load(f"data/tts_{name}.wav")
    ref = Path(f"data/tts_{name}.txt").read_text(encoding="utf-8-sig").strip()
    if name == "short": e.transcribe(audio, language="en")  # warm-up
    r = e.transcribe(audio, language="en")
    out[name] = {"audio_s": round(r.duration, 1), "time_s": round(r.seconds, 2), "x_realtime": round(r.duration / r.seconds, 1), "wer": round(wer(ref, r.text), 4)}
out["vram_mb_delta"] = vram() - v0
out["ram_mb"] = round(proc.memory_info().rss / 2**20)
print("RESULT " + json.dumps(out))
