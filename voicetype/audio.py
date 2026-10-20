"""Microphone capture (16 kHz mono float32)."""
import threading

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


class MicError(RuntimeError):
    pass


def list_inputs() -> list[tuple[int, str]]:
    """Input devices on the default host API, so one physical mic is not listed several times."""
    host = sd.query_hostapis(sd.default.hostapi)["name"]
    return [(i, d["name"]) for i, d in enumerate(sd.query_devices())
            if d["max_input_channels"] > 0 and sd.query_hostapis(d["hostapi"])["name"] == host]


class Recorder:
    """Push-to-talk style capture. stop() returns audio; cancel() discards it."""

    NO_SPEECH_SECONDS = 10  # give up if nothing loud was heard for this long (only when auto-stop is on)

    def __init__(self, device: int | None = None, max_seconds: float = 300, on_limit=None,
                 silence_seconds: float = 0, silence_threshold: float = 0.01):
        """silence_seconds > 0 enables auto-stop: after speech was heard, that long below silence_threshold (peak) stops it."""
        self.device, self.max_samples, self.on_limit = device, int(max_seconds * SAMPLE_RATE), on_limit
        self.silence_samples, self.threshold = int(silence_seconds * SAMPLE_RATE), silence_threshold
        self._heard, self._quiet = False, 0
        self._chunks: list[np.ndarray] = []
        self._n = 0
        self._stream = None
        self._limit_hit = False
        self._lock = threading.Lock()

    @property
    def recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        if self._stream:
            return
        self._chunks, self._n, self._limit_hit = [], 0, False
        self._heard, self._quiet = False, 0
        try:
            self._stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                          device=self.device, callback=self._cb)
            self._stream.start()
        except Exception as e:
            self._close()
            raise MicError(f"Microphone unavailable: {e}") from e

    def _cb(self, indata, frames, time_info, status):
        with self._lock:
            self._chunks.append(indata[:, 0].copy())
            self._n += frames
            hit = self._n >= self.max_samples
            if self.silence_samples:
                if float(np.abs(indata).max()) >= self.threshold:
                    self._heard, self._quiet = True, 0
                else:
                    self._quiet += frames
                stopped_after_speech = self._heard and self._quiet >= self.silence_samples
                gave_up = not self._heard and self._n >= self.NO_SPEECH_SECONDS * SAMPLE_RATE
                hit = hit or stopped_after_speech or gave_up
            hit = hit and not self._limit_hit
            self._limit_hit = self._limit_hit or hit
        if hit and self.on_limit:
            # never stop a stream from inside its own callback
            threading.Thread(target=self.on_limit, daemon=True).start()

    def _close(self) -> None:
        s, self._stream = self._stream, None
        if s is not None:
            try:
                s.stop()
            finally:
                s.close()

    def stop(self) -> np.ndarray:
        self._close()
        with self._lock:
            audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, "float32")
            self._chunks = []
        return audio[: self.max_samples]

    def cancel(self) -> None:
        self._close()
        with self._lock:
            self._chunks = []


def record(seconds: float, device: int | None = None) -> np.ndarray:
    try:
        data = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32", device=device)
        sd.wait()
    except Exception as e:
        raise MicError(f"Microphone unavailable: {e}") from e
    return data[:, 0]
