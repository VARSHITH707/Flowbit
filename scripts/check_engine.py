"""Integration checks 2.5/2.7/2.8: CPU, languages, offline. Run: python scripts/check_engine.py"""
import sys, wave
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from voicetype import models
from voicetype.speech import Engine

def load(p):
    w = wave.open(p); return np.frombuffer(w.readframes(w.getnframes()), '<i2').astype('float32') / 32768

short = load("data/tts_short.wav")
print("available small:", models.is_available("small"), "| bogus:", models.is_available("small-nope"))
e = Engine("small", device="cpu"); r = e.transcribe(short, language="en")
print(f"CPU: device={r.device} {r.seconds:.2f}s ->", r.text)
e = Engine("small", device="auto", offline=True)
r = e.transcribe(short)  # auto-detect
print(f"AUTO-DETECT: lang={r.language} ->", r.text)
r = e.transcribe(short, language="en"); print("MANUAL en ->", r.text)
