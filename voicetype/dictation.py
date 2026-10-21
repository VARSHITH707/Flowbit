"""Dictation controller: IDLE -> RECORDING -> PROCESSING -> INSERTING -> DONE (success) -> IDLE, or FAILED.
UI-agnostic (callbacks). One session at a time: duplicate starts, stops and late results are ignored."""
import logging
import threading
import time
from dataclasses import dataclass

from . import insertion
from .audio import MicError, Recorder

log = logging.getLogger(__name__)
IDLE, RECORDING, PROCESSING, INSERTING, DONE, FAILED = "idle", "recording", "processing", "inserting", "done", "failed"
ACTIVE = (RECORDING, PROCESSING, INSERTING)
AUTO_STOP = {"silence": "Stopped automatically after a pause in your speech.",
             "no_speech": "Stopped: no speech was heard.", "limit": "Stopped at the longest recording length."}


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
        self.mode = ""  # "hold" or "toggle": how the current recording was started
        self._lock = threading.RLock()
        self._rec = None
        self._target = 0
        self._gen = 0  # bumped by cancel; a stale worker must not insert
        self._stopped_at = 0.0  # when the last recording stopped: start of the stop-to-insert timing

    def _set(self, state, detail="") -> None:
        self.state = state
        self.on_state(state, detail)

    def toggle(self) -> None:
        self.stop() if self.state == RECORDING else self.start("toggle")

    def start(self, mode: str = "hold") -> None:
        with self._lock:
            if self.state in ACTIVE:
                return
            self._target = self._fg()
            self.mode, self._auto_note = mode, ""
            silence = self.s.silence_seconds if mode == "toggle" else 0  # never auto-stop while a key is held
            self._rec = self._make_recorder(self.s.device, self.s.max_seconds, self._auto_stop, silence, self.s.silence_threshold)
            try:
                self._rec.start()
            except MicError as e:
                self._rec = None
                self._set(FAILED, str(e))
                return
            self._set(RECORDING)

    def _auto_stop(self) -> None:
        """The recorder stopped by itself (pause, no speech, longest length): say why, then finish normally."""
        self._auto_note = AUTO_STOP.get(getattr(self._rec, "stop_reason", ""), "")
        self.stop()

    def stop(self) -> None:
        with self._lock:
            if self.state != RECORDING:
                return
            self._stopped_at = time.perf_counter()
            audio = self._rec.stop()
            self._rec = None
            if len(audio) < self.s.min_seconds * 16000:
                self._set(IDLE, "Recording too short; ignored.")
                return
            gen, target = self._gen, self._target
            self._set(PROCESSING)
        threading.Thread(target=self._work, args=(audio, gen, target), daemon=True, name="transcribe").start()

    def level(self) -> float:
        """Live microphone peak (0-1) while recording, else 0: drives the moving on-screen indicator."""
        rec = self._rec
        return getattr(rec, "level", 0.0) if rec is not None else 0.0

    def cancel(self) -> None:
        with self._lock:
            self._gen += 1
            if self._rec:
                self._rec.cancel()
                self._rec = None
            if self.state in ACTIVE:
                self._set(IDLE, "Cancelled.")

    def _work(self, audio, gen, target) -> None:
        t_stop = self._stopped_at
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
        note = getattr(self, "_auto_note", "")
        log.info("timing (s): recording=%.2f asr=%.3f", res.duration, res.seconds)
        if self.s.auto_insert:
            with self._lock:
                if gen != self._gen or self.state != PROCESSING:  # cancelled or already finalised: never insert twice
                    return
                self._set(INSERTING)
            t_ins = time.perf_counter()
            ins = self._insert(res.text, target)
            log.info("timing (s): insert=%.3f stop_to_insert=%.3f", time.perf_counter() - t_ins, time.perf_counter() - t_stop)
            if gen != self._gen:
                return
            if ins.status != "inserted":
                self.on_result(res, ins)
                self._set(DONE, ins.detail)
                return
        self.on_result(res, None)
        self._set(DONE, note)
