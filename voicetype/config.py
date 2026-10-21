"""Persistent settings (JSON in the app folder's userdata\\). Bad values fall back to defaults; writes are atomic."""
import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from . import APP_DIR  # the project folder, or the .exe's folder: everything Flowbit writes lives there
from .hotkeys import DEFAULTS as HOTKEY_DEFAULTS, parse

log = logging.getLogger(__name__)

MODELS_DIR = APP_DIR / "models"  # speech models (Hugging Face cache layout)


def data_dir() -> Path:
    """Settings, history, memory and log: <app folder>\\userdata. VOICETYPE_HOME overrides it (used by tests)."""
    p = Path(os.environ.get("VOICETYPE_HOME") or APP_DIR / "userdata")
    p.mkdir(parents=True, exist_ok=True)
    return p


_SKIP = object()
CHOICES = {
    "device": ("auto", "cuda", "cpu"),
    "recording_mode": ("both", "hold", "toggle"),
    "theme": ("system", "dark", "light"),
    "insertion_method": ("auto", "paste", "type"),
    "focus_policy": ("copy", "insert_anyway"),
    "format_mode": ("smart", "exact"),
}
STYLES = ("formal", "casual")
DEFAULT_STYLES = {"email": "formal", "work": "formal", "personal": "casual", "code": "formal", "other": "formal"}


@dataclass
class Config:
    model: str = "large-v3-turbo"
    device: str = "auto"
    language: str = "en"  # "" = auto-detect
    mic: int | None = None
    hotkeys: dict = field(default_factory=lambda: dict(HOTKEY_DEFAULTS))
    recording_mode: str = "both"
    max_seconds: int = 300
    silence_stop: bool = False
    silence_seconds: float = 2.0
    silence_threshold: float = 0.01
    auto_insert: bool = True
    insertion_method: str = "auto"
    focus_policy: str = "copy"  # what to do when focus changed during recording
    theme: str = "dark"
    mascot_visible: bool = True  # the floating Flowbit mascot (always shown while recording)
    mascot_opacity: float = 0.9
    mascot_pos: list | None = None  # [x, y] of its top-left corner; None = bottom centre of the main screen
    reduced_motion: bool = False
    history_enabled: bool = True
    history_days: int = 0  # 0 = keep until deleted
    vocab: list = field(default_factory=list)
    vocab_bias: bool = False  # feed the glossary to the recogniser; can make Whisper add words, so opt-in
    format_mode: str = "smart"  # smart = lists, numbers, commands, punctuation; exact = words as recognised
    ai_cleanup: bool = True  # Smart mode: local AI also removes fillers and self-corrections (Ollama, this PC)
    ai_punctuation: bool = True  # local AI adds missing punctuation to run-on speech; words may never change
    number_formatting: bool = True
    spoken_commands: bool = True  # "new line", "new paragraph", "bullet point" ... in Smart mode
    commands_in_exact: bool = False  # also obey spoken commands in Exact mode
    preview: bool = False  # show the text and ask before inserting it
    llm_model: str = "qwen2.5:7b-instruct-q4_K_M"
    styles: dict = field(default_factory=lambda: dict(DEFAULT_STYLES))
    learn_from_edits: bool = True
    unload_minutes: int = 10
    first_run_done: bool = False

    @classmethod
    def path(cls) -> Path:
        return data_dir() / "settings.json"

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        p = cls.path()
        if not p.exists():
            return cfg
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("settings root is not an object")
        except Exception as e:
            bad = p.with_suffix(".corrupt.json")
            p.replace(bad)
            log.warning("settings unreadable (%s); moved to %s and using defaults", e, bad.name)
            return cfg
        return cfg._apply(raw)

    def _apply(self, raw: dict) -> "Config":
        raw = dict(raw)
        old = raw.get("cleanup_mode")  # settings from before Flowbit: smart / clean / exact
        if "format_mode" not in raw and old in ("smart", "clean", "exact"):
            raw["format_mode"] = "exact" if old == "exact" else "smart"
            raw.setdefault("ai_cleanup", old == "smart")
        if "mascot_visible" not in raw and isinstance(raw.get("show_idle_pill"), bool):
            raw["mascot_visible"] = raw["show_idle_pill"]
        for f in fields(self):
            if f.name in raw:
                v = self._coerce(f.name, raw[f.name], getattr(self, f.name))
                if v is not _SKIP:
                    setattr(self, f.name, v)
        self.max_seconds = min(max(self.max_seconds, 5), 3600)
        self.mascot_opacity = min(max(self.mascot_opacity, 0.3), 1.0)
        return self

    def _coerce(self, name: str, v, cur):
        """Return a valid value for `name`, or _SKIP to keep the current/default one."""
        is_num = isinstance(v, (int, float)) and not isinstance(v, bool)
        if name in CHOICES:
            return v if v in CHOICES[name] else _SKIP
        if name == "hotkeys":
            return self._clean_hotkeys(v)
        if name == "styles":
            return {k: (v.get(k) if isinstance(v, dict) and v.get(k) in STYLES else d) for k, d in DEFAULT_STYLES.items()}
        if name == "mic":
            return v if v is None or (isinstance(v, int) and not isinstance(v, bool)) else _SKIP
        if name == "mascot_pos":
            ok = isinstance(v, list) and len(v) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in v)
            return v if ok or v is None else _SKIP
        if name == "vocab":
            return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else cur
        if isinstance(cur, bool):
            return v if isinstance(v, bool) else _SKIP
        if isinstance(cur, (int, float)):
            return type(cur)(v) if is_num else _SKIP
        if isinstance(cur, str):
            return v if isinstance(v, str) else _SKIP
        return v

    @staticmethod
    def _clean_hotkeys(v) -> dict:
        out = dict(HOTKEY_DEFAULTS)
        if isinstance(v, dict):
            for k in out:
                if isinstance(v.get(k), str):
                    try:
                        parse(v[k])
                        out[k] = v[k]
                    except ValueError:
                        pass
        return out

    def save(self) -> None:
        p = self.path()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, p)
