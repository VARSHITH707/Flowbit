"""Dictation controller: idle -> recording -> processing -> done/failed. UI-agnostic (callbacks)."""
import logging
import threading
from dataclasses import dataclass

from . import insertion
from .audio import MicError, Recorder

log = logging.getLogger(__name__)
IDLE, RECORDING, PROCESSING, DONE, FAILED = "idle", "recording", "processing", "done", "failed"


@dataclass
class Settings:
    device: int | None = None
    max_seconds: float = 300
    language: str | None = "en"
    auto_insert: bool = True
    min_seconds: float = 0.3  # shorter than this is treated as an accidental tap
    silence_seconds: float = 0  # >0: stop automatically after this much silence following speech
    silence_threshold: float = 0.01


class Dictation:
    def __init__(self, get_engine, settings: Settings, on_state=lambda s, d="": None,
                 on_result=lambda result, ins: None, recorder_factory=Recorder, insert=insertion.insert,
                 foreground=insertion.foreground, categorize=lambda hwnd: "other"):
        self.get_engine, self.s = get_engine, settings
        self.on_state, self.on_result = on_state, on_result
        self._make_recorder, self._insert, self._fg, self._categorize = recorder_factory, insert, foreground, categorize
        self.last_target = 0  # window the last result was inserted into
        self.state = IDLE
        self._lock = threading.RLock()
        self._rec = None
        self._target = 0
        self._gen = 0  # bumped by cancel; a stale worker must not insert

    def _set(self, state, detail="") -> None:
        self.state = state
        self.on_state(state, detail)

    def toggle(self) -> None:
        self.stop() if self.state == RECORDING else self.start()

    def start(self) -> None:
        with self._lock:
            if self.state in (RECORDING, PROCESSING):
                return
            self._target = self._fg()
            self._rec = self._make_recorder(self.s.device, self.s.max_seconds, self.stop, self.s.silence_seconds, self.s.silence_threshold)
            try:
                self._rec.start()
            except MicError as e:
                self._rec = None
                self._set(FAILED, str(e))
                return
            self._set(RECORDING)

    def stop(self) -> None:
        with self._lock:
            if self.state != RECORDING:
                return
            audio = self._rec.stop()
            self._rec = None
            if len(audio) < self.s.min_seconds * 16000:
                self._set(IDLE, "Recording too short; ignored.")
                return
            gen, target = self._gen, self._target
            self._set(PROCESSING)
        threading.Thread(target=self._work, args=(audio, gen, target), daemon=True, name="transcribe").start()

    def cancel(self) -> None:
        with self._lock:
            self._gen += 1
            if self._rec:
                self._rec.cancel()
                self._rec = None
            if self.state in (RECORDING, PROCESSING):
                self._set(IDLE, "Cancelled.")

    def _work(self, audio, gen, target) -> None:
        try:
            res = self.get_engine().transcribe(audio, language=self.s.language, category=self._categorize(target))
        except Exception as e:  # TranscribeError or engine load failure: never insert on failure
            if gen == self._gen:
                log.error("transcription failed: %s", e)
                self._set(FAILED, str(e))
            return
        if gen != self._gen:  # cancelled while processing: drop the text
            return
        self.last_target = target
        if self.s.auto_insert:
            ins = self._insert(res.text, target)
            if ins.status != "inserted":
                self.on_result(res, ins)
                self._set(DONE, ins.detail)
                return
        self.on_result(res, None)
        self._set(DONE)
