"""Local transcription with faster-whisper. Never returns text on failure."""
import time
from dataclasses import dataclass

import numpy as np

from .cuda import add_cuda_dll_dirs


class TranscribeError(RuntimeError):
    pass


@dataclass
class Result:
    text: str
    language: str
    duration: float
    seconds: float
    device: str
    raw: str = ""  # recognised text before any cleanup
    note: str = ""  # e.g. why AI cleanup was skipped


class Engine:
    def __init__(self, model="small", device="auto", compute_type=None, offline=False):
        add_cuda_dll_dirs()
        self.name, self.offline, self.notice = model, offline, None
        want = "cuda" if device == "auto" and _cuda_ok() else ("cpu" if device == "auto" else device)
        t = time.perf_counter()
        try:
            self._load(want, compute_type)
        except Exception as e:
            if want == "cuda":  # fall back to CPU instead of failing
                self.notice = f"GPU unavailable ({_short(e)}); using CPU."
                try:
                    self._load("cpu", None)
                except Exception as e2:
                    raise TranscribeError(f"Model load failed: {e2}") from e2
            else:
                raise TranscribeError(f"Model load failed on {want}: {e}") from e
        self.load_seconds = time.perf_counter() - t

    def _load(self, device, compute_type):
        from faster_whisper import WhisperModel

        from . import models
        ct = compute_type or ("int8_float16" if device == "cuda" else "int8")
        self.model = WhisperModel(models.model_ref(self.name), device=device, compute_type=ct, local_files_only=self.offline)
        self.device = device

    def transcribe(self, audio: np.ndarray, language: str | None = None, vocab: str | None = None) -> Result:
        if audio is None or len(audio) < 1600 or float(np.abs(audio).max()) < 1e-4:
            raise TranscribeError("No audio captured (empty or silent recording).")
        t = time.perf_counter()
        try:
            segs, info = self.model.transcribe(audio, language=language, vad_filter=True,
                                               initial_prompt=vocab, beam_size=5)
            text = " ".join(s.text.strip() for s in segs).strip()
        except Exception as e:
            if self.device == "cuda" and _is_gpu_error(e):  # e.g. out of memory: retry once on CPU
                self.notice = f"GPU error ({_short(e)}); retried on CPU."
                self._load("cpu", None)
                return self.transcribe(audio, language, vocab)
            raise TranscribeError(f"Transcription failed: {e}") from e
        if not text:
            raise TranscribeError("No speech detected.")
        return Result(text, info.language, info.duration, time.perf_counter() - t, self.device)


def _cuda_ok() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def _is_gpu_error(e: Exception) -> bool:
    m = str(e).lower()
    return any(k in m for k in ("out of memory", "cuda", "cublas", "cudnn"))


def _short(e: Exception) -> str:
    return str(e).splitlines()[0][:120]
