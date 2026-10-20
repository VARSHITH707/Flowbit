import json
import time

import pytest

from voicetype.config import Config
from voicetype.history import History


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICETYPE_HOME", str(tmp_path))
    return tmp_path


def test_data_and_models_live_in_the_app_folder(monkeypatch):
    from voicetype import config, models
    monkeypatch.delenv("VOICETYPE_HOME")
    assert config.data_dir() == config.APP_DIR / "userdata"
    assert models.MODELS_DIR == config.APP_DIR / "models"
    assert (config.APP_DIR / "voicetype" / "config.py").exists()  # APP_DIR is the project root


def test_defaults_when_missing():
    c = Config.load()
    assert c.model == "large-v3-turbo" and c.language == "en" and c.history_enabled


def test_save_load_roundtrip():
    c = Config.load()
    c.model, c.theme, c.language, c.vocab = "small", "dark", "", ["PySide6", "Kubernetes"]
    c.hotkeys["toggle"] = "ctrl+alt+f9"
    c.save()
    d = Config.load()
    assert (d.model, d.theme, d.language, d.vocab, d.hotkeys["toggle"]) == ("small", "dark", "", ["PySide6", "Kubernetes"], "ctrl+alt+f9")


def test_corrupt_file_backed_up_and_defaults(home):
    (home / "settings.json").write_text("{not json", encoding="utf-8")
    c = Config.load()
    assert c.model == "large-v3-turbo" and (home / "settings.corrupt.json").exists()


def test_bad_values_ignored_individually(home):
    (home / "settings.json").write_text(json.dumps({
        "theme": "neon", "max_seconds": "lots", "auto_insert": "yes", "model": "small",
        "hotkeys": {"hold": "ctrl+banana", "toggle": "ctrl+f9"}, "mic": "usb"}), encoding="utf-8")
    c = Config.load()
    assert c.theme == "system" and c.max_seconds == 300 and c.auto_insert is True and c.model == "small"
    assert c.hotkeys["hold"] == "ctrl+alt+d" and c.hotkeys["toggle"] == "ctrl+f9" and c.mic is None


def test_max_seconds_clamped(home):
    (home / "settings.json").write_text(json.dumps({"max_seconds": 999999}), encoding="utf-8")
    assert Config.load().max_seconds == 3600


def test_history_add_search_delete_clear():
    h = History()
    a = h.add("Hello world", "en", 1.5, "small")
    h.add("Kubernetes cluster 100% ready_now", "en", 2.0, "small")
    assert [e.text for e in h.list("hello")] == ["Hello world"]
    assert len(h.list("100%")) == 1 and len(h.list("%")) == 1  # LIKE wildcards are literal
    assert len(h.list("ready_now")) == 1 and h.list("readyXnow") == []
    h.delete(a)
    assert len(h.list()) == 1
    h.clear()
    assert h.list() == []


def test_history_persists_across_instances(home):
    h = History(); h.add("kept", "en", 1, "m"); h.close()
    assert [e.text for e in History().list()] == ["kept"]


def test_history_prune_and_export(home):
    h = History()
    h.add("old"); h.db.execute("UPDATE entries SET ts = ?", (time.time() - 10 * 86400,)); h.db.commit()
    h.add("new", raw="before cleanup")
    assert h.prune(5) == 1 and [e.text for e in h.list()] == ["new"]
    for fmt, name in (("json", "o.json"), ("csv", "o.csv"), ("txt", "o.txt")):
        out = h.export(home / name, fmt)
        assert "new" in out.read_text(encoding="utf-8-sig")
    for name in ("o.csv", "o.txt"):  # original wording is exported too
        assert "before cleanup" in (home / name).read_text(encoding="utf-8-sig")
    with pytest.raises(ValueError):
        h.export(home, "json")
    with pytest.raises(ValueError):
        h.export(home / "x", "xml")


def test_clear_really_removes_text_from_the_file(home):
    h = History()
    h.add("SECRET_MARKER_ZEBRA_12345 " * 20)
    h.close()
    assert b"SECRET_MARKER_ZEBRA_12345" in (home / "history.db").read_bytes()  # sanity: it was written
    h = History()
    h.clear()
    h.close()
    assert b"SECRET_MARKER_ZEBRA_12345" not in (home / "history.db").read_bytes()


def test_delete_one_removes_that_text_from_listing_and_search(home):
    h = History()
    i = h.add("remove me please")
    h.add("keep me")
    h.delete(i)
    assert h.list("remove") == [] and [e.text for e in h.list()] == ["keep me"]


def test_single_delete_overwrites_text_in_the_file(home):
    h = History()
    i = h.add("SECRET_SINGLE_DELETE_QWERTY " * 10)
    h.add("another entry stays")
    h.close()
    assert b"SECRET_SINGLE_DELETE_QWERTY" in (home / "history.db").read_bytes()
    h = History()
    h.delete(i)
    h.close()
    raw = (home / "history.db").read_bytes()
    assert b"SECRET_SINGLE_DELETE_QWERTY" not in raw and b"another entry stays" in raw
