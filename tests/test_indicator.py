"""The on-screen logo: still when not recording, moving while recording (and taller when you speak louder)."""
from voicetype.dictation import DONE, IDLE, PROCESSING, RECORDING, Dictation, Settings
from voicetype.ui.pill import IDLE_BARS, StatePill, bar_heights


def test_logo_is_still_when_idle_and_moves_while_recording():
    assert bar_heights(IDLE, 0.0, 0.5) == bar_heights(IDLE, 7.3, 0.9) == list(IDLE_BARS)
    assert bar_heights(RECORDING, 0.0, 0.0) != bar_heights(RECORDING, 0.1, 0.0)  # moves even during a pause
    assert bar_heights(PROCESSING, 0.0, 0.0) != bar_heights(PROCESSING, 0.1, 0.0)


def test_louder_voice_makes_taller_bars():
    quiet = sum(sum(bar_heights(RECORDING, t / 30, 0.0)) for t in range(60))
    loud = sum(sum(bar_heights(RECORDING, t / 30, 0.2)) for t in range(60))
    assert loud > quiet * 1.5
    assert all(0 <= h <= 1 for t in range(60) for h in bar_heights(RECORDING, t / 30, 5.0))  # clipping is capped


def test_animation_runs_only_while_recording_or_transcribing(qapp):
    p = StatePill()
    p.set_state(IDLE)
    assert not p.animating and p.width() < 60  # small logo, no text
    p.set_state(RECORDING)
    assert p.animating and p.width() > 60  # logo + "Listening 0:00"
    p.set_state(PROCESSING)
    assert p.animating
    p.set_state(DONE)
    assert not p.animating
    p.hide()


def test_dictation_reports_live_mic_level_only_while_recording():
    class Rec:
        level = 0.42
        def start(self): pass  # noqa: E704
        def cancel(self): pass  # noqa: E704

    d = Dictation(lambda: None, Settings(), recorder_factory=lambda *a: Rec())
    assert d.level() == 0.0
    d.start()
    assert d.state == RECORDING and d.level() == 0.42
    d.cancel()
    assert d.level() == 0.0
