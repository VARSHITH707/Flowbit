"""6.1: prove the dictation path makes no network calls. Every socket connect/DNS lookup raises; transcription must still work."""
import os
import socket
import sys
import tempfile
import wave
from pathlib import Path

os.environ["VOICETYPE_HOME"] = tempfile.mkdtemp(prefix="vt_offline_")
os.environ["HF_HUB_OFFLINE"] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
attempts, local = [], []
LOOPBACK = ("127.0.0.1", "localhost", "::1")
_connect, _getaddrinfo, _create = socket.socket.connect, socket.getaddrinfo, socket.create_connection


def _host(a):
    return a[0] if isinstance(a, tuple) else a


def guarded_connect(self, address, *a, **k):
    if _host(address) in LOOPBACK:
        local.append(_host(address))  # the local AI (Ollama) on this PC: allowed
        return _connect(self, address, *a, **k)
    attempts.append(address)
    raise OSError("network blocked for the offline test")


def guarded_getaddrinfo(host, *a, **k):
    if host in LOOPBACK:
        return _getaddrinfo(host, *a, **k)
    attempts.append(host)
    raise OSError("network blocked for the offline test")


def guarded_create(address, *a, **k):
    if _host(address) in LOOPBACK:
        local.append(_host(address))
        return _create(address, *a, **k)
    attempts.append(address)
    raise OSError("network blocked for the offline test")


socket.socket.connect = guarded_connect
socket.getaddrinfo = guarded_getaddrinfo
socket.create_connection = guarded_create

import numpy as np

from voicetype.config import Config
from voicetype.transcriber import Transcriber

w = wave.open(str(ROOT / "data/tts_short.wav"))
audio = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype("float32") / 32768
for model in ("small", "large-v3-turbo"):
    for mode in ("exact", "smart"):
        cfg = Config()
        cfg.model, cfg.cleanup_mode = model, mode
        out = Transcriber(lambda: cfg).transcribe(audio, language="en")
        print(f"{model} / {mode}: {out.text!r} on {out.device} {('(AI note: ' + out.note + ')') if out.note else ''}")
print("connections to this PC only (local AI):", len(local))
print("network connection attempts during model load + transcription:", len(attempts), attempts[:3])
sys.exit(0 if not attempts else 1)
