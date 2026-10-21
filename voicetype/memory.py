"""Local memory: what Flowbit learns from your corrections. Plain JSON in userdata\\memory inside the app folder.

learned.json   word corrections learned from your edits   {"heard": "...", "written": "...", "count": n, ...}
examples.json  your recent edits of AI-cleaned text (cleaned -> what you kept), used as style examples
README.txt     what these files are; delete the folder to forget everything
"""
import difflib
import json
import os
import re
import threading
import time
from pathlib import Path

from .config import data_dir

MAX_EXAMPLES = 20
REPEATS_TO_ACTIVATE = 2  # non-name corrections must be made twice before they apply
_SKIP = re.compile(r"[\d/\\:@_=<>{}()\[\]#$%^&*+|~`]|https?|www\.|\.(com|org|net|io|py|js)\b", re.IGNORECASE)
_COMMON = set("a an the and or but to of in on at for with is are was were be been it this that these those i you he she we they "
              "my your our their me him her us them not no yes so do does did have has had will would can could should "
              "there here then than as by from up down out if".split())
README = """Flowbit memory (everything stays on this PC)

learned.json   Words Flowbit learned when you corrected its typing. Next time it writes them your way.
examples.json  Recent edits you made to AI-cleaned text; a few are shown to the local AI as examples of your style.

Delete an entry in the app (Memory tab) or edit these files while Flowbit is closed.
Delete this whole folder to make Flowbit forget everything it learned.
"""


def memory_dir() -> Path:
    p = data_dir() / "memory"
    p.mkdir(parents=True, exist_ok=True)
    readme = p / "README.txt"
    if not readme.exists():
        readme.write_text(README, encoding="utf-8")
    return p


def _load(name: str) -> list:
    f = memory_dir() / name
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except Exception:
        f.replace(f.with_suffix(".corrupt.json"))
        return []


def _save(name: str, data: list) -> None:
    f = memory_dir() / name
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, f)


_lock = threading.Lock()


# ---------- learning rules
def is_learnable(heard: str, written: str) -> bool:
    """A spelling/name fix, not a content change. Mirrors Wispr's skip list (no URLs, code, numbers...)."""
    h, w = heard.strip(), written.strip()
    if not h or not w or h == w or len(h) > 60 or len(w) > 60:
        return False
    if len(h.split()) > 3 or len(w.split()) > 3 or _SKIP.search(h) or _SKIP.search(w):
        return False
    if h.lower() == w.lower():
        return True  # capitalization fix, e.g. kubernetes -> Kubernetes
    if h.lower() in _COMMON and w.lower() in _COMMON:
        return False  # grammar edit, not a word the recogniser got wrong
    a, b = re.sub(r"\W", "", h.lower()), re.sub(r"\W", "", w.lower())
    # 0.7: conservative on purpose. Learning a wrong rule (Friday->Monday scores 0.5) is worse than missing a right one;
    # you can always add a word by hand.
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.7


def looks_like_name(heard: str, written: str) -> bool:
    """Names/brands (you capitalised it, or it has inner capitals like PySide6) are trusted after one correction.
    Anything else could be a one-off grammar/content edit, so it only takes effect when you repeat it."""
    w = written.strip()
    return any(c.isupper() for c in w[1:]) or (w[:1].isupper() and heard.strip()[:1].islower())


def corrections_from_edit(inserted: str, final: str) -> list[tuple[str, str]]:
    """Word substitutions the user made inside the text Flowbit inserted."""
    a, b = inserted.split(), final.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "replace" and (i2 - i1) <= 3 and (j2 - j1) <= 3:
            heard = re.sub(r"^\W+|\W+$", "", " ".join(a[i1:i2]))
            written = re.sub(r"^\W+|\W+$", "", " ".join(b[j1:j2]))
            if is_learnable(heard, written):
                out.append((heard, written))
    return out


# ---------- learned corrections
def learned() -> list[dict]:
    return _load("learned.json")


def learn(pairs: list[tuple[str, str]], source: str = "edit") -> list[tuple[str, str]]:
    """Add/refresh learned corrections. Returns the pairs that were new."""
    if not pairs:
        return []
    with _lock:
        data, new, now = learned(), [], time.time()
        index = {d["heard"].lower(): d for d in data}
        for heard, written in pairs:
            d = index.get(heard.lower())
            if d:
                same = d["written"] == written
                d.update(written=written, count=d.get("count", 1) + 1 if same else 1, last=now)
            else:
                d = {"heard": heard, "written": written, "count": 1, "first": now, "last": now, "source": source}
                data.append(d)
                index[heard.lower()] = d
                new.append((heard, written))
        _save("learned.json", data)
    return new


def forget(heard: str) -> None:
    with _lock:
        _save("learned.json", [d for d in learned() if d["heard"].lower() != heard.lower()])


def is_active(d: dict) -> bool:
    return looks_like_name(d["heard"], d["written"]) or d.get("count", 1) >= REPEATS_TO_ACTIVATE


def vocab_entries() -> list[str]:
    """Active learned corrections in the vocabulary format used by textproc ('heard=>written')."""
    return [f"{d['heard']}=>{d['written']}" for d in learned() if is_active(d)]


# ---------- style examples from your edits
def examples() -> list[tuple[str, str]]:
    return [(e["cleaned"], e["final"]) for e in _load("examples.json")]


def add_example(cleaned: str, final: str) -> bool:
    """Keep small, real edits of AI output (not rewrites of everything) as style examples."""
    if cleaned.strip() == final.strip():
        return False
    ratio = difflib.SequenceMatcher(None, cleaned, final).ratio()
    if ratio < 0.6 or len(final) > 600:
        return False
    with _lock:
        data = _load("examples.json")
        data.append({"cleaned": cleaned, "final": final, "time": time.time()})
        _save("examples.json", data[-MAX_EXAMPLES:])
    return True


def clear_all() -> None:
    with _lock:
        for name in ("learned.json", "examples.json"):
            (memory_dir() / name).unlink(missing_ok=True)


# ---------- app categories (for per-app style)
CATEGORIES = ("email", "work", "personal", "code", "other")
_APPS = {
    "email": ("outlook", "thunderbird", "hxoutlook", "olk", "mailspring"),
    "work": ("slack", "teams", "ms-teams", "zoom", "webex"),
    "personal": ("whatsapp", "telegram", "discord", "signal", "messenger"),
    "code": ("code", "cursor", "windsurf", "pycharm", "idea64", "devenv", "sublime_text", "notepad++", "windowsterminal", "powershell", "cmd"),
}
_TITLES = {"email": ("gmail", "outlook", "proton mail", "mail -"), "work": ("slack", "teams"), "personal": ("whatsapp", "telegram", "discord")}


def app_category(exe: str, title: str = "") -> str:
    name = os.path.splitext(os.path.basename(exe or ""))[0].lower()
    for cat, names in _APPS.items():
        if name in names:
            return cat
    t = (title or "").lower()
    for cat, words in _TITLES.items():  # web apps inside a browser, recognised by window title
        if any(w in t for w in words):
            return cat
    return "other"
