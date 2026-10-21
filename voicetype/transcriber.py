"""Lazy-loaded, reloadable transcription front end used by the dictation controller."""
import dataclasses
import logging
import threading
import time

from . import cleanup, formatting, memory, models, textproc
from .speech import Engine, Result, TranscribeError

log = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, get_config, on_status=lambda msg: None):
        self.get_config, self.on_status = get_config, on_status
        self._engine: Engine | None = None
        self._key = None
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()  # one transcription at a time (a cancelled run may still be finishing)
        self._last_used = time.time()
        self.notice: str | None = None

    @property
    def loaded(self) -> bool:
        return self._engine is not None

    @property
    def loaded_model(self) -> str | None:
        return self._key[0] if self._engine is not None and self._key else None

    def engine(self) -> Engine:
        cfg = self.get_config()
        key = (cfg.model, cfg.device)
        with self._lock:
            if self._engine is None or key != self._key:
                self._engine = None
                if not models.is_available(cfg.model):
                    raise TranscribeError(f"Model '{cfg.model}' is not downloaded yet. Open the Models tab to download it.")
                self.on_status(f"Loading {cfg.model}...")
                self._engine = Engine(cfg.model, device=cfg.device, offline=True)
                self._key = key
                self.notice = self._engine.notice
                self.on_status(f"Model ready on {self._engine.device}")
            return self._engine

    def transcribe(self, audio, language=None, category: str = "other") -> Result:
        """Speech -> text. `category` is the kind of app being dictated into (memory.app_category)."""
        cfg = self.get_config()
        with self._run_lock:
            eng = self.engine()
            res = eng.transcribe(audio, language=language or None, vocab=textproc.vocab_prompt(cfg.vocab) if cfg.vocab_bias else None)
        self._last_used = time.time()
        text, note = self.format(res.text, cfg, category)
        if not text.strip():
            raise TranscribeError("No speech detected.")
        return dataclasses.replace(res, text=text, raw=res.text, note=note)

    @staticmethod
    def format(raw: str, cfg, category: str = "other") -> tuple[str, str]:
        """Recognised text -> text to insert, plus a note when an optional AI step was skipped.

        Exact : words as recognised; spacing only (+ spoken commands if enabled, + AI punctuation that may not
                change any word). Smart: fillers removed, optional AI cleanup, then the deterministic formatter
                (lists, numbers, commands, capitals, sentence ends). Your vocabulary is applied last, so it wins."""
        vocab = list(cfg.vocab) + memory.vocab_entries()  # your words + words learned from your corrections
        note, used_ai = "", False
        if cfg.format_mode == "exact":
            text = formatting.format_exact(raw)
            if cfg.commands_in_exact:
                text = formatting.normalize_spacing(formatting.spoken_commands(text))
        else:
            text = textproc.clean(textproc.apply_vocab(raw, vocab))  # your spellings reach the AI already fixed
            if cfg.spoken_commands:  # explicit cues first, so the AI receives (and keeps) the finished structure
                text = formatting.lists(formatting.spoken_commands(text))
            style = cfg.styles.get(category, "formal")
            if cfg.ai_cleanup and text.strip():
                terms = tuple(dict.fromkeys(w for _, w in textproc.parse_vocab(vocab)))
                c = cleanup.clean(text, cfg.llm_model, style=style, terms=terms, examples=tuple(memory.examples()))
                text, note, used_ai = formatting.keep_line_breaks(text, c.text), c.note, c.used_llm
        if cfg.ai_punctuation and not used_ai and cleanup.needs_punctuation(text):
            p = cleanup.punctuate(text, cfg.llm_model)
            text, note = p.text, (note if p.used_llm else p.note)
        if cfg.format_mode == "smart":
            text = formatting.format_smart(text, cfg.number_formatting, cfg.spoken_commands)
        text = textproc.apply_vocab(text, vocab)
        if cfg.format_mode == "smart" and cfg.styles.get(category) == "casual" and category in ("personal", "work"):
            text = textproc.drop_single_trailing_period(text)
        return text, note

    def unload_if_idle(self, minutes: float) -> bool:
        """Free VRAM after `minutes` without use (0 = never)."""
        with self._lock:
            if self._engine is None or minutes <= 0 or time.time() - self._last_used < minutes * 60:
                return False
            self._engine = None
            self._key = None
        import gc
        gc.collect()
        log.info("model unloaded after idle")
        return True

    def unload(self) -> None:
        with self._lock:
            self._engine = None
            self._key = None
        import gc
        gc.collect()
