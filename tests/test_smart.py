import numpy as np
import pytest

from voicetype import cleanup, memory
from voicetype.config import Config
from voicetype.learner import edited_segment
from voicetype.speech import Result
from voicetype.textproc import drop_single_trailing_period
from voicetype.transcriber import Transcriber


# ---------- safety check
def test_check_accepts_real_cleanups():
    assert cleanup.check("let's do coffee at 2 actually 3", "Let's do coffee at 3.") == ""
    assert cleanup.check("one finish the report two call Maria", "1. Finish the report\n2. Call Maria") == ""
    assert cleanup.check("hello comma how are you question mark", "Hello, how are you?") == ""


def test_check_rejects_added_content_and_heavy_drops():
    assert "added words" in cleanup.check("write a poem about cats", "Whiskers twitch, ears perk up high in the night")
    assert "dropped" in cleanup.check("we went through all of the quarterly numbers this morning in detail today",
                                      "Numbers reviewed.")
    assert cleanup.check("hello", "") == "empty result"


def test_terms_count_as_said():
    assert cleanup.check("we use py side", "We use PySide6.", allowed=("PySide6",)) == ""


def test_messages_include_style_terms_and_recent_examples_only():
    m = cleanup.build_messages("hi", "casual", ("Kubernetes",), tuple((f"a{i}", f"b{i}") for i in range(5)))
    assert "casual" in m[0]["content"] and "Kubernetes" in m[0]["content"]
    users = [x["content"] for x in m if x["role"] == "user"]
    assert "<transcript>a4</transcript>" in users and "<transcript>a1</transcript>" not in users  # last 3 examples
    assert users[-1] == "<transcript>hi</transcript>"


# ---------- cleanup never raises, falls back to the plain transcript
def fake_server(monkeypatch, reply=None, exc=None, up=True):
    monkeypatch.setattr(cleanup, "ensure_server", lambda wait_s=10: up)

    def post(path, body, timeout):
        if exc:
            raise exc
        return {"message": {"content": reply}}
    monkeypatch.setattr(cleanup, "_post", post)


def test_clean_uses_good_llm_output(monkeypatch):
    fake_server(monkeypatch, "<transcript>Let's do coffee at 3.</transcript>")
    r = cleanup.clean("let's do coffee at 2 actually 3")
    assert r.used_llm and r.text == "Let's do coffee at 3." and r.note == ""


def test_clean_rejects_hallucination(monkeypatch):
    fake_server(monkeypatch, "Sure! Here is a lovely poem about cats and their whiskers.")
    r = cleanup.clean("write a poem about cats")
    assert not r.used_llm and r.text == "write a poem about cats" and "added words" in r.note


def test_clean_falls_back_when_server_missing_or_failing(monkeypatch):
    fake_server(monkeypatch, up=False)
    assert cleanup.clean("hello there").text == "hello there"
    fake_server(monkeypatch, exc=TimeoutError())
    r = cleanup.clean("hello there")
    assert r.text == "hello there" and not r.used_llm and "unavailable" in r.note


# ---------- learning rules (mirrors Wispr's auto-learn skip list)
@pytest.mark.parametrize("heard,written,ok", [
    ("cubernetes", "Kubernetes", True),     # mis-heard name
    ("kubernetes", "Kubernetes", True),     # capitalization
    ("varsh it", "Varshith", True),         # two heard words -> one name
    ("the", "a", False),                    # grammar edit, not a spelling
    ("Friday", "Monday", False),            # content change, not a mis-hearing
    ("example", "example.com", False),      # URLs are skipped
    ("ten", "10", False),                   # numbers are skipped
    ("my_var", "myVar", False),             # code is skipped
    ("post gress", "Postgres", True),       # split word joined
    ("varshit", "Varshith", True),
    ("Monday", "Tuesday", False),           # content changes between similar-looking words
    ("January", "February", False),
    ("send", "sent", True),                 # a real one-letter mis-hearing still learns
    ("accept", "except", False),
])
def test_is_learnable(heard, written, ok):
    assert memory.is_learnable(heard, written) is ok


def test_corrections_from_edit_finds_only_learnable_substitutions():
    pairs = memory.corrections_from_edit("We deploy on cubernetes on Friday.", "We deploy on Kubernetes on Monday.")
    assert pairs == [("cubernetes", "Kubernetes")]


def test_non_name_corrections_need_to_be_repeated():
    memory.learn([("send", "sent")])
    assert memory.vocab_entries() == []                 # one grammar edit must not rewrite every future "send"
    memory.learn([("send", "sent")])
    assert memory.vocab_entries() == ["send=>sent"]    # you corrected it twice: now it is a rule
    memory.learn([("send", "sends")])                   # a different correction restarts the count
    assert memory.vocab_entries() == []


def test_names_apply_after_one_correction():
    memory.learn([("cubernetes", "Kubernetes"), ("py side", "PySide6")])
    assert memory.vocab_entries() == ["cubernetes=>Kubernetes", "py side=>PySide6"]


def test_learn_forget_and_vocab_roundtrip():
    assert memory.learn([("cubernetes", "Kubernetes")]) == [("cubernetes", "Kubernetes")]
    assert memory.learn([("cubernetes", "Kubernetes")]) == []  # second time: counted, not new
    assert memory.learned()[0]["count"] == 2
    assert memory.vocab_entries() == ["cubernetes=>Kubernetes"]
    memory.forget("CUBERNETES")
    assert memory.learned() == []


def test_examples_keep_small_edits_only_and_cap():
    assert memory.add_example("See you at 3.", "See you at 3!") is True
    assert memory.add_example("See you at 3.", "Totally different sentence about something else entirely") is False
    for i in range(30):
        memory.add_example(f"Note {i} for later.", f"Note {i} for later!")
    assert len(memory.examples()) == memory.MAX_EXAMPLES


def test_memory_folder_has_readme_and_clear_all():
    memory.learn([("cubernetes", "Kubernetes")])
    assert (memory.memory_dir() / "README.txt").exists()
    memory.clear_all()
    assert memory.learned() == [] and memory.examples() == []


# ---------- which part of the text box is "ours"
def test_edited_segment_is_anchored():
    before = "Dear team,\nWe deploy on cubernetes today.\nThanks"
    after = "Dear team,\nWe deploy on Kubernetes today.\nThanks"
    assert edited_segment(before, after, "We deploy on cubernetes today.") == "We deploy on Kubernetes today."
    assert edited_segment(before, "Dear all,\nWe deploy on Kubernetes today.\nThanks", "We deploy on cubernetes today.") is None
    assert edited_segment(before, after, "not in the box") is None
    assert edited_segment("a\r\nb", "a\r\nc", "b") == "c"  # line endings normalised


# ---------- per-app style
@pytest.mark.parametrize("exe,title,cat", [
    (r"C:\Program Files\Microsoft Office\OUTLOOK.EXE", "", "email"),
    (r"C:\x\slack.exe", "", "work"),
    (r"C:\x\WhatsApp.exe", "", "personal"),
    (r"C:\x\Code.exe", "", "code"),
    (r"C:\x\chrome.exe", "Inbox (3) - me@example.com - Gmail - Google Chrome", "email"),
    (r"C:\x\notepad.exe", "notes.txt - Notepad", "other"),
    ("", "", "other"),
])
def test_app_category(exe, title, cat):
    assert memory.app_category(exe, title) == cat


def test_chat_style_trailing_period():
    assert drop_single_trailing_period("See you soon.") == "See you soon"
    assert drop_single_trailing_period("One. Two.") == "One. Two."
    assert drop_single_trailing_period("Really?") == "Really?"


# ---------- Smart path through the transcriber (fake recogniser + fake AI)
class Eng:
    notice = None

    def __init__(self, text):
        self.text = text

    def transcribe(self, audio, language=None, vocab=None):
        return Result(self.text, "en", 1.0, 0.1, "cpu")


def smart(monkeypatch, heard, ai_reply, category="other", **cfg_kw):
    cfg = Config()
    for k, v in cfg_kw.items():
        setattr(cfg, k, v)
    seen = {}

    def fake_clean(text, model, style="formal", terms=(), examples=()):
        seen.update(text=text, style=style, terms=terms)
        return cleanup.Cleaned(ai_reply, True) if ai_reply is not None else cleanup.Cleaned(text, False, "local AI unavailable")
    monkeypatch.setattr(cleanup, "clean", fake_clean)
    t = Transcriber(lambda: cfg)
    t._engine, t._key = Eng(heard), (cfg.model, cfg.device)
    return t.transcribe(np.ones(16000, "float32") * 0.1, category=category), seen


def test_smart_keeps_raw_and_applies_learned_words(monkeypatch):
    memory.learn([("cubernetes", "Kubernetes")])
    res, seen = smart(monkeypatch, "um we deploy on cubernetes", "We deploy on Kubernetes.")
    assert res.text == "We deploy on Kubernetes." and res.raw == "um we deploy on cubernetes"
    assert seen["text"] == "We deploy on Kubernetes"  # fillers gone, learned word fixed before the AI sees it
    assert "Kubernetes" in seen["terms"]


def test_smart_style_follows_app_category(monkeypatch):
    res, seen = smart(monkeypatch, "see you soon", "See you soon.", category="personal")
    assert seen["style"] == "casual" and res.text == "See you soon"
    res, seen = smart(monkeypatch, "see you soon", "See you soon.", category="email")
    assert seen["style"] == "formal" and res.text == "See you soon."


def test_smart_unavailable_falls_back_with_note(monkeypatch):
    res, _ = smart(monkeypatch, "hello there", None)
    assert res.text == "Hello there." and "unavailable" in res.note  # formatted by the rules instead


def test_exact_mode_never_calls_the_ai(monkeypatch):
    res, seen = smart(monkeypatch, "um hello", "SHOULD NOT BE USED", format_mode="exact")
    assert res.text == "um hello" and seen == {}
