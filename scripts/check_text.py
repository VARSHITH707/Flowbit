"""Checks 5.2/5.3 on real audio: punctuation fidelity and custom vocabulary effect (TTS reference clips)."""
import difflib
import os
import re
import sys
import tempfile

import _projtmp  # noqa: F401  (temp files stay in the project)
import wave
from pathlib import Path

os.environ["VOICETYPE_HOME"] = tempfile.mkdtemp(prefix="vt_text_")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np

from voicetype.config import Config
from voicetype.transcriber import Transcriber


def load(n):
    w = wave.open(str(ROOT / f"data/tts_{n}.wav"))
    return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype("float32") / 32768


ref = (ROOT / "data/tts_long.txt").read_text(encoding="utf-8-sig").strip()
cfg = Config()
cfg.model = "large-v3-turbo"
tr = Transcriber(lambda: cfg)
audio = load("long")
for label, vocab in (("no vocabulary", []), ("with vocabulary", ["Kubernetes", "PostgreSQL", "PySide6", "PySide six=>PySide6", "PySide 6=>PySide6"])):
    cfg.vocab = vocab
    out = tr.transcribe(audio, language="en").text
    ratio = difflib.SequenceMatcher(None, ref, out).ratio()
    terms = {t: len(re.findall(re.escape(t), out)) for t in ("Kubernetes", "PostgreSQL", "PySide6")}
    sentences_ref, sentences_out = ref.count("."), out.count(".")
    print(f"[{label}] raw char similarity {ratio:.4f} | periods ref={sentences_ref} out={sentences_out} | exact term counts {terms} (expected 14 each)")
    print("   sample:", out[:150].replace("\n", " "))
    if label == "no vocabulary":
        print("   raw variants of 'PySide':", sorted(set(re.findall(r"Py\s?Side\s?\w+", out)))[:5], "| Kubernetes variants:", sorted(set(re.findall(r"[Kk]uber\w+", out)))[:5], "| Postgres variants:", sorted(set(re.findall(r"[Pp]ostgre\w+", out)))[:5])
