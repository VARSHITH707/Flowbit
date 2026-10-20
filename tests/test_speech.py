import numpy as np
import pytest

from voicetype.speech import Engine, TranscribeError


def fake_engine(model, device="cuda"):
    e = Engine.__new__(Engine)
    e.model, e.device, e.name, e.offline, e.notice = model, device, "x", False, None
    return e


class Seg:
    text = " hello world "


class Info:
    language, duration = "en", 1.0


class OKModel:
    def transcribe(self, *a, **k):
        return [Seg()], Info()


class OOMModel:
    def transcribe(self, *a, **k):
        raise RuntimeError("CUDA failed with error out of memory")


class EmptyModel:
    def transcribe(self, *a, **k):
        return [], Info()


TONE = (np.sin(np.linspace(0, 2000, 16000)) * 0.1).astype("float32")


def test_empty_audio_is_error_not_text():
    with pytest.raises(TranscribeError):
        fake_engine(OKModel()).transcribe(np.zeros(0, "float32"))


def test_silent_audio_is_error_not_text():
    with pytest.raises(TranscribeError):
        fake_engine(OKModel()).transcribe(np.zeros(16000, "float32"))


def test_no_speech_is_error_not_fabricated():
    with pytest.raises(TranscribeError):
        fake_engine(EmptyModel(), "cpu").transcribe(TONE)


def test_success_returns_stripped_text():
    assert fake_engine(OKModel(), "cpu").transcribe(TONE).text == "hello world"


def test_gpu_oom_retries_on_cpu_with_notice():
    e = fake_engine(OOMModel())
    e._load = lambda device, ct: (setattr(e, "model", OKModel()), setattr(e, "device", device))
    r = e.transcribe(TONE)
    assert r.text == "hello world" and r.device == "cpu" and "retried on CPU" in e.notice


def test_other_errors_not_swallowed():
    class Bad:
        def transcribe(self, *a, **k):
            raise ValueError("boom")
    with pytest.raises(TranscribeError):
        fake_engine(Bad(), "cpu").transcribe(TONE)
