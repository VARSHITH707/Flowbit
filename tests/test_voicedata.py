import numpy as np
import pytest

from voicetype import voicedata as vd
from voicetype.audio import SAMPLE_RATE


def tone(seconds):
    return (0.3 * np.sin(np.arange(int(seconds * SAMPLE_RATE)) / 10)).astype("float32")


def test_save_load_roundtrip_and_delete_last():
    a = vd.save(tone(2), "  Hello   world ", baseline="hello word")
    b = vd.save(tone(1), "Second clip")
    assert [e["text"] for e in vd.load()] == ["Hello world", "Second clip"]
    assert a["seconds"] == 2.0 and (vd.voice_dir() / a["audio"]).exists()
    assert np.allclose(vd.read_audio(a), tone(2), atol=1e-3)  # 16-bit WAV keeps the audio
    assert vd.delete_last() == b and not (vd.voice_dir() / b["audio"]).exists()
    assert [e["text"] for e in vd.load()] == ["Hello world"]


def test_sample_rate_matches_the_recorder():
    assert vd.SAMPLE_RATE == SAMPLE_RATE


def test_save_rejects_empty_text_and_bad_lengths():
    for audio, text in ((tone(2), "  "), (tone(0.2), "too short"), (tone(29), "too long")):
        with pytest.raises(ValueError):
            vd.save(audio, text)
    assert vd.load() == []


def test_trained_model_is_found_only_once_built_and_never_downloaded(tmp_path, monkeypatch):
    from voicetype import models
    monkeypatch.setattr(models, "MODELS_DIR", tmp_path)
    assert "my-voice" in models.MODELS and not models.is_available("my-voice")
    with pytest.raises(ValueError):
        models.download("my-voice")
    (tmp_path / "my-voice").mkdir()
    (tmp_path / "my-voice" / "model.bin").write_bytes(b"x")
    assert models.is_available("my-voice") and models.model_ref("my-voice") == str(tmp_path / "my-voice")
    assert models.delete("my-voice") and not (tmp_path / "my-voice").exists() and tmp_path.exists()


def test_word_error_rate_ignores_case_and_punctuation():
    assert vd.word_errors("Hello, world!", "hello world") == (0, 2)
    assert vd.word_errors("push it to GitHub", "push it to get hub") == (2, 4)  # 1 substitution + 1 insertion
    assert vd.wer([("a b c d", "a b c d"), ("a b", "a x")]) == pytest.approx(1 / 6)
    assert vd.wer([]) == 0.0
