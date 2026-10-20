import time

import numpy as np

from voicetype.audio import MicError
from voicetype.dictation import DONE, FAILED, IDLE, PROCESSING, RECORDING, Dictation, Settings
from voicetype.insertion import InsertResult
from voicetype.speech import Result, TranscribeError

GOOD = np.ones(16000, "float32") * 0.1


class FakeRec:
    fail = False
    audio = GOOD

    def __init__(self, device, max_seconds, on_limit, *rest):
        self.cancelled = False

    def start(self):
        if FakeRec.fail:
            raise MicError("Microphone unavailable: test")

    def stop(self):
        return FakeRec.audio

    def cancel(self):
        self.cancelled = True


class FakeEngine:
    def __init__(self, text="hello", delay=0.0, err=None):
        self.text, self.delay, self.err = text, delay, err

    def transcribe(self, audio, language=None, vocab=None, **kw):
        time.sleep(self.delay)
        if self.err:
            raise self.err
        return Result(self.text, "en", 1.0, 0.1, "cpu")


def make(engine, **kw):
    states, inserted, results = [], [], []
    d = Dictation(lambda: engine, Settings(**kw), on_state=lambda s, det="": states.append((s, det)),
                  on_result=lambda t, r: results.append((t, r)), recorder_factory=FakeRec,
                  insert=lambda t, h: (inserted.append((t, h)), InsertResult("inserted"))[1], foreground=lambda: 42)
    return d, states, inserted, results


def wait(cond, t=3):
    end = time.time() + t
    while time.time() < end and not cond():
        time.sleep(0.01)
    return cond()


def test_happy_path_inserts_into_original_target():
    d, states, inserted, _ = make(FakeEngine())
    d.start(); d.stop()
    assert wait(lambda: d.state == DONE) and inserted == [("hello", 42)]
    assert [s for s, _ in states] == [RECORDING, PROCESSING, DONE]


def test_cancel_while_recording_inserts_nothing():
    d, states, inserted, _ = make(FakeEngine())
    d.start(); d.cancel(); d.stop()
    time.sleep(0.2)
    assert inserted == [] and d.state == IDLE


def test_cancel_while_processing_inserts_nothing():
    d, states, inserted, _ = make(FakeEngine(delay=0.4))
    d.start(); d.stop()
    assert d.state == PROCESSING
    d.cancel(); time.sleep(0.7)
    assert inserted == [] and d.state == IDLE


def test_transcription_error_is_reported_not_inserted():
    d, states, inserted, _ = make(FakeEngine(err=TranscribeError("No speech detected.")))
    d.start(); d.stop()
    assert wait(lambda: d.state == FAILED) and inserted == [] and states[-1][1] == "No speech detected."


def test_mic_unavailable_fails_cleanly_and_recovers():
    d, states, inserted, _ = make(FakeEngine())
    FakeRec.fail = True
    try:
        d.start()
        assert d.state == FAILED and "Microphone" in states[-1][1]
    finally:
        FakeRec.fail = False
    d.start()
    assert d.state == RECORDING  # recovery after the mic returns


def test_too_short_recording_ignored():
    FakeRec.audio = np.ones(100, "float32") * 0.1
    try:
        d, states, inserted, _ = make(FakeEngine())
        d.start(); d.stop()
        assert d.state == IDLE and inserted == []
    finally:
        FakeRec.audio = GOOD


def test_start_ignored_while_processing():
    d, *_ = make(FakeEngine(delay=0.3))
    d.start(); d.stop(); d.start()
    assert d.state == PROCESSING


# ---- silence auto-stop (Recorder logic, driven with synthetic chunks; no microphone needed)
from voicetype.audio import SAMPLE_RATE, Recorder  # noqa: E402


def feed(rec, seconds, level):
    n = int(seconds * SAMPLE_RATE)
    rec._cb(np.full((n, 1), level, "float32"), n, None, None)


def test_silence_autostop_fires_after_speech_then_pause():
    fired = []
    r = Recorder(silence_seconds=1.5, silence_threshold=0.01, on_limit=lambda: fired.append(1))
    feed(r, 0.5, 0.0)   # leading silence does not stop it
    feed(r, 2.0, 0.2)   # speech
    feed(r, 1.0, 0.0)   # short pause: keep going
    time.sleep(0.05)
    assert fired == []
    feed(r, 0.6, 0.0)   # pause reaches 1.6 s
    assert wait(lambda: fired == [1])


def test_speech_resets_the_pause_timer():
    fired = []
    r = Recorder(silence_seconds=1.0, silence_threshold=0.01, on_limit=lambda: fired.append(1))
    feed(r, 1.0, 0.3)
    for _ in range(4):
        feed(r, 0.8, 0.0)
        feed(r, 0.2, 0.3)  # keeps talking before the pause is long enough
    time.sleep(0.1)
    assert fired == []


def test_no_speech_gives_up_and_disabled_means_never():
    fired = []
    r = Recorder(silence_seconds=1.0, on_limit=lambda: fired.append(1))
    feed(r, 9.0, 0.0)
    time.sleep(0.05)
    assert fired == []
    feed(r, 1.5, 0.0)
    assert wait(lambda: fired == [1])
    fired2 = []
    r2 = Recorder(silence_seconds=0, on_limit=lambda: fired2.append(1))  # feature off
    feed(r2, 1.0, 0.3)
    feed(r2, 30.0, 0.0)
    time.sleep(0.1)
    assert fired2 == []


def test_result_object_reaches_on_result_with_language_and_duration():
    d, states, inserted, results = make(FakeEngine("hi there"))
    d.start(); d.stop()
    assert wait(lambda: d.state == DONE)
    res, ins = results[-1]
    assert res.text == "hi there" and res.language == "en" and res.duration == 1.0 and ins is None


def test_transcriptions_never_overlap_on_the_same_model():
    import threading

    from voicetype.config import Config
    from voicetype.transcriber import Transcriber

    active, peak, lock = [0], [0], threading.Lock()

    class Eng:
        notice = None

        def transcribe(self, audio, language=None, vocab=None):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.15)
            with lock:
                active[0] -= 1
            return Result("x", "en", 1.0, 0.1, "cpu")

    cfg = Config()
    t = Transcriber(lambda: cfg)
    t._engine, t._key = Eng(), (cfg.model, cfg.device)
    ths = [threading.Thread(target=t.transcribe, args=(np.ones(16000, "float32") * 0.1,)) for _ in range(4)]
    [x.start() for x in ths]
    [x.join() for x in ths]
    assert peak[0] == 1
