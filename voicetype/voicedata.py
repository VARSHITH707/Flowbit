"""Your voice dataset for fine-tuning: recordings you choose to save, each with the exact text you said.

Unlike dictation (audio is never kept), these clips ARE saved: that is their purpose. They live only in
userdata\\voice\\ inside the app folder (excluded from git). dataset.jsonl has one line per clip.
"""
import json
import re
import time
import wave
from pathlib import Path

import numpy as np

from .audio import SAMPLE_RATE
from .config import data_dir

MIN_SECONDS, MAX_SECONDS = 0.5, 28  # Whisper trains on 30-second windows


def voice_dir() -> Path:
    p = data_dir() / "voice"
    (p / "clips").mkdir(parents=True, exist_ok=True)
    return p


def _index() -> Path:
    return voice_dir() / "dataset.jsonl"


def load() -> list[dict]:
    f = _index()
    if not f.exists():
        return []
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]


def save(audio: np.ndarray, text: str, baseline: str = "", source: str = "free") -> dict:
    """Store one clip. `text` must be exactly what was said; `baseline` is what the current model heard."""
    text = " ".join(text.split())
    secs = len(audio) / SAMPLE_RATE
    if not text:
        raise ValueError("Type exactly what you said before saving.")
    if not MIN_SECONDS <= secs <= MAX_SECONDS:
        raise ValueError(f"Clips must be {MIN_SECONDS}-{MAX_SECONDS} seconds long (this one is {secs:.1f} s).")
    name = f"{time.time_ns() // 1000}.wav"
    with wave.open(str(voice_dir() / "clips" / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
    entry = {"audio": f"clips/{name}", "text": text, "baseline": baseline, "source": source,
             "seconds": round(secs, 2), "ts": time.time()}
    with _index().open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def delete_last() -> dict | None:
    entries = load()
    if not entries:
        return None
    last = entries.pop()
    (voice_dir() / last["audio"]).unlink(missing_ok=True)
    _index().write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
    return last


def read_audio(entry: dict) -> np.ndarray:
    with wave.open(str(voice_dir() / entry["audio"]), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype("float32") / 32767


def _words(s: str) -> list[str]:
    return re.sub(r"[^\w\s']", " ", s.lower()).split()


def word_errors(ref: str, hyp: str) -> tuple[int, int]:
    """(word edits needed to turn hyp into ref, words in ref). Case and punctuation are ignored."""
    r, h = _words(ref), _words(hyp)
    row = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        prev, row[0] = row[0], i
        for j, hw in enumerate(h, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (rw != hw))
    return row[-1], len(r)


def wer(pairs: list[tuple[str, str]]) -> float:
    """Word error rate over (reference, hypothesis) pairs, 0.0-1.0+."""
    errs = [word_errors(r, h) for r, h in pairs]
    total = sum(n for _, n in errs)
    return sum(e for e, _ in errs) / total if total else 0.0
