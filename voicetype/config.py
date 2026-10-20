"""Persistent settings (JSON in %APPDATA%\\VoiceType). Bad values fall back to defaults; writes are atomic."""
import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .hotkeys import DEFAULTS as HOTKEY_DEFAULTS, parse

log = logging.getLogger(__name__)


def data_dir() -> Path:
    """VOICETYPE_HOME overrides the location (used by tests)."""
    base = os.environ.get("VOICETYPE_HOME") or os.path.join(os.environ.get("APPDATA", str(Path.home())), "VoiceType")
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p


_SKIP = object()
CHOICES = {
    "device": ("auto", "cuda", "cpu"),
    "recording_mode": ("both", "hold", "toggle"),
    "theme": ("system", "dark", "light"),
    "insertion_method": ("auto", "paste", "type"),
    "focus_policy": ("copy", "insert_anyway"),
    "cleanup_mode": ("smart", "clean", "exact"),
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
    theme: str = "system"
    show_idle_pill: bool = True
    history_enabled: bool = True
    history_days: int = 0  # 0 = keep until deleted
    vocab: list = field(default_factory=list)
    vocab_bias: bool = False  # feed the glossary to the recogniser; can make Whisper add words, so opt-in
    cleanup_mode: str = "smart"  # smart = local AI cleanup (falls back to plain text when unavailable)
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
        for f in fields(self):
            if f.name in raw:
                v = self._coerce(f.name, raw[f.name], getattr(self, f.name))
                if v is not _SKIP:
                    setattr(self, f.name, v)
        self.max_seconds = min(max(self.max_seconds, 5), 3600)
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
