"""Smart mode for real: spoken clip -> Whisper (GPU) -> local AI cleanup (Ollama) -> final text.
Run scripts\\make_smart_clips.ps1 first."""
import os
import re
import sys
import tempfile
import time
import wave
from pathlib import Path

os.environ["VOICETYPE_HOME"] = tempfile.mkdtemp(prefix="vt_smart_")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np

from voicetype import cleanup
from voicetype.config import Config
from voicetype.transcriber import Transcriber

CASES = {  # clip: (must contain, must not contain, list items or None)
    "coffee": (["coffee at three", "coffee at 3"], ["two", " 2"], None),
    "scratch": (["Tuesday"], ["Monday", "scratch"], None),
    "points": (["open the laptop", "email it to the team", "archive the old files"], ["milk", "no, no"], 7),
    "punct": (["Hello, how are you?"], ["comma", "question mark"], None),
    "question": (["capital of France"], ["Paris"], None),
    "plain": (["quarterly numbers", "board next week"], [], None),
}


def load(name):
    w = wave.open(str(ROOT / f"data/smart_{name}.wav"))
    return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype("float32") / 32768


cfg = Config()
cfg.cleanup_mode = "smart"
t = Transcriber(lambda: cfg)
t.engine()
print("local AI warm:", cleanup.warm_up(cfg.llm_model))
res_all = []
for name, (must, must_not, items) in CASES.items():
    t0 = time.perf_counter()
    r = t.transcribe(load(name), language="en")
    sec = time.perf_counter() - t0
    low = r.text.lower()
    ok_must = any(m.lower() in low for m in must) if name == "coffee" else all(m.lower() in low for m in must)
    ok_not = not any(m.lower() in low for m in must_not)
    n_items = len(re.findall(r"(?m)^\s*\d+[.)]\s+\S", r.text))
    ok_items = items is None or n_items == items
    ok = ok_must and ok_not and ok_items and not r.note
    res_all.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} {name:<9} {sec:.2f}s total (speech+AI)  note={r.note!r}")
    print(f"     heard : {r.raw}")
    print(f"     typed : {r.text!r}")
print(f"{sum(res_all)}/{len(res_all)} passed")
sys.exit(0 if all(res_all) else 1)
