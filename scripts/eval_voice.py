"""Is the fine-tuned model better? (step 3 of 3). Runs the real VoiceType engine (faster-whisper) on:
  1. your held-out clips: recorded by you, never used for training (listed in models\\<name>\\training.json)
  2. reference clips with known text (data\\tts_*.wav): checks the model did not get worse at plain English

  .\\.venv\\Scripts\\python.exe scripts\\eval_voice.py            [--name my-voice] [--base large-v3-turbo]

Writes models\\<name>\\eval.json. Switch to it in Settings -> Model only if it says BETTER.
"""
import argparse
import json
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import _projtmp  # noqa: E402,F401
import numpy as np  # noqa: E402

from voicetype import models  # noqa: E402
from voicetype import voicedata as vd  # noqa: E402
from voicetype.speech import Engine, TranscribeError  # noqa: E402


def reference_clips() -> list[tuple[np.ndarray, str]]:
    out = []
    for wav in sorted((ROOT / "data").glob("tts_*.wav")):
        txt = wav.with_suffix(".txt")
        if txt.exists() and wav.stat().st_size < 4_000_000:  # skip the 5-minute clip: slow, adds little
            with wave.open(str(wav)) as w:
                a = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype("float32") / 32767
            out.append((a, txt.read_text(encoding="utf-8").strip()))
    return out


def score(model: str, clips, language: str) -> tuple[float, float]:
    eng = Engine(model, offline=True)
    pairs, t = [], time.perf_counter()
    for audio, ref in clips:
        try:
            pairs.append((ref, eng.transcribe(audio, language).text))
        except TranscribeError:
            pairs.append((ref, ""))
    secs = (time.perf_counter() - t) / max(1, len(clips))
    del eng
    return vd.wer(pairs), secs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="my-voice")
    ap.add_argument("--base", default="large-v3-turbo")
    a = ap.parse_args()
    if not models.is_available(a.name):
        sys.exit(f"{a.name} is not trained yet: run scripts\\train_voice.py first.")
    info = json.loads((models.local_path(a.name) / "training.json").read_text(encoding="utf-8"))
    held_paths = set(info["held_out"])
    held = [(vd.read_audio(e), e["text"]) for e in vd.load() if e["audio"] in held_paths]
    ref = reference_clips()
    res = {}
    for label, clips in (("your voice (held out)", held), ("reference English", ref)):
        if not clips:
            continue
        b, bs = score(a.base, clips, info["language"])
        t, ts = score(a.name, clips, info["language"])
        res[label] = {"clips": len(clips), "base_wer": round(b, 4), "tuned_wer": round(t, 4),
                      "base_s_per_clip": round(bs, 2), "tuned_s_per_clip": round(ts, 2)}
        print(f"{label:24s} {len(clips):3d} clips   {a.base}: {b:6.1%}   {a.name}: {t:6.1%}   "
              f"({bs:.2f} s vs {ts:.2f} s per clip)")
    mine, eng = res.get("your voice (held out)"), res.get("reference English")
    better = bool(mine) and mine["tuned_wer"] < mine["base_wer"] and (not eng or eng["tuned_wer"] <= eng["base_wer"] + 0.01)
    res["verdict"] = "BETTER" if better else "NOT BETTER"
    (models.local_path(a.name) / "eval.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nVerdict: {res['verdict']}" + (" - switch to it in Settings -> Model." if better else
          " - keep using the base model; record more clips and train again."))
    if mine and mine["clips"] < 20:
        print(f"Caution: only {mine['clips']} held-out clips, so this comparison is rough.")


if __name__ == "__main__":
    main()
