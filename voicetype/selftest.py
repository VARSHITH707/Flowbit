"""Headless diagnostic: load the model, transcribe a WAV, write the result as JSON.

Used to verify an install (including the packaged .exe, which has no console):
    VoiceType.exe --selftest sample.wav --selftest-out result.json [--model small]
"""
import json
import sys
import time
import wave

import numpy as np


def run(wav_path: str, out_path: str, model: str = "small") -> int:
    info: dict = {"model": model, "frozen": bool(getattr(sys, "frozen", False)), "python": sys.version.split()[0]}
    code = 1
    try:
        from . import models
        from .speech import Engine

        info["model_available"] = models.is_available(model)
        with wave.open(wav_path) as w:
            if w.getframerate() != 16000 or w.getnchannels() != 1 or w.getsampwidth() != 2:
                raise ValueError("expected a 16 kHz mono 16-bit WAV")
            audio = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype("float32") / 32768
        t = time.perf_counter()
        engine = Engine(model, offline=True)
        info["load_seconds"] = round(time.perf_counter() - t, 2)
        res = engine.transcribe(audio, language="en")
        info.update(device=res.device, seconds=round(res.seconds, 2), text=res.text, notice=engine.notice)
        code = 0
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {e}"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)
    return code
