"""Try dictation in a language with your own voice. Records from the microphone, prints what was recognised.

  .\.venv\Scripts\python.exe scripts\try_language.py hi            # Hindi, 8 seconds
  .\.venv\Scripts\python.exe scripts\try_language.py ta 10 small   # Tamil, 10 s, small model
  .\.venv\Scripts\python.exe scripts\try_language.py auto          # auto-detect the language

Nothing is saved: audio stays in memory. Language codes: en hi ta te ml bn kn mr gu pa ur es fr de ar ja ko zh ...
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from voicetype import models
from voicetype.audio import record
from voicetype.speech import Engine, TranscribeError

lang = sys.argv[1] if len(sys.argv) > 1 else "en"
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 8
model = sys.argv[3] if len(sys.argv) > 3 else "large-v3-turbo"
if not models.is_available(model):
    sys.exit(f"Model {model} is not downloaded. Run: python -c \"from voicetype import models; models.download('{model}')\"")

engine = Engine(model, offline=True)
print(f"Model {model} on {engine.device}. Language: {lang}")
for n in (3, 2, 1):
    print(f"Speak in {n}...", end="\r")
    time.sleep(1)
print(f"RECORDING for {secs:.0f} s - speak now!        ")
audio = record(secs)
print("Transcribing...")
try:
    r = engine.transcribe(audio, language=None if lang == "auto" else lang)
    print(f"\nDetected language: {r.language}   ({r.seconds:.1f} s to transcribe)\n\n{r.text}\n")
except TranscribeError as e:
    print(f"\nNo text: {e}\n")
