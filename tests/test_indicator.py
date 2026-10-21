"""The Flowbit mascot: shows the real state, moves only when it should, never takes focus, stays on screen."""
from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QPainter

from voicetype.dictation import DONE, FAILED, IDLE, INSERTING, PROCESSING, RECORDING, Dictation, Settings
from voicetype.ui.mascot import ACTIVE_MS, IDLE_MS, Mascot, bob_offset, mascot_icon, paint_mascot, status_text, wave_strength


def render(state, t=0.0, level=0.0, reduced=False) -> bytes:
    img = QImage(60, 60, QImage.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    paint_mascot(p, 0, 0, 60, state, t, level, reduced)
    p.end()
    return bytes(img.constBits())


def test_sound_waves_follow_the_microphone_only_while_recording(qapp):
    assert wave_strength(IDLE, 0.5) == wave_strength(PROCESSING, 0.5) == 0.0
    assert wave_strength(RECORDING, 0.2) > wave_strength(RECORDING, 0.0) > 0  # visible even in a pause
    assert render(RECORDING, level=0.0) != render(RECORDING, level=0.3)  # louder voice looks different


def test_idle_floats_gently_but_reduced_motion_is_still(qapp):
    assert bob_offset(IDLE, 0.5, False) != bob_offset(IDLE, 1.5, False)
    assert bob_offset(IDLE, 0.5, True) == bob_offset(IDLE, 1.5, True) == 0.0
    assert bob_offset(RECORDING, 0.5, False) == 0.0
    assert render(IDLE, 0.3, reduced=True) == render(IDLE, 2.9, reduced=True)


def test_every_state_draws_differently(qapp):
    frames = {s: render(s, 1.0, 0.1) for s in (IDLE, RECORDING, PROCESSING, DONE, FAILED)}
    assert len(set(frames.values())) == 5
    assert not mascot_icon(32).isNull()


def test_status_bubble_says_what_is_happening_and_that_it_is_local():
    assert status_text(IDLE, "", 0, "") == ""
    assert "on this PC" in status_text(RECORDING, "", 0, "toggle") and "click" in status_text(RECORDING, "", 0, "toggle")
    assert status_text(PROCESSING, "", 0, "") == "Transcribing on this PC"
    assert status_text(FAILED, "Microphone unavailable: x\nmore", 0, "") == "Microphone unavailable: x"


def test_animation_timer_matches_state_and_settings(qapp):
    m = Mascot()
    m.configure(visible=True, opacity=0.8, reduced=False, pos=None)
    assert m.frame_ms == IDLE_MS and abs(m.windowOpacity() - 0.8) < 0.01
    m.set_state(RECORDING, mode="hold")
    assert m.frame_ms == ACTIVE_MS and m.windowOpacity() == 1.0 and m.width() > 60  # mascot + bubble
    m.set_state(INSERTING)
    assert m.animating
    m.configure(visible=True, opacity=0.8, reduced=True, pos=None)
    m.set_state(IDLE)
    assert not m.animating  # reduced motion: no idle animation at all
    m.configure(visible=False, opacity=0.8, reduced=False, pos=None)
    assert not m.isVisible() and not m.animating  # hidden when idle: costs nothing
    m.hide()


def test_position_is_kept_on_screen(qapp):
    m = Mascot()
    far = m.clamp(QPoint(10**6, 10**6))
    near = m.clamp(QPoint(-10**6, -10**6))
    from PySide6.QtGui import QGuiApplication
    g = QGuiApplication.primaryScreen().availableGeometry()
    assert g.contains(far) and g.contains(near)
    m.configure(True, 0.9, True, [g.left() + 5, g.top() + 5])
    assert m.pos() == QPoint(g.left() + 5, g.top() + 5)
    m.hide()


def test_click_toggles_and_drag_moves(qapp):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    m = Mascot()
    m.configure(True, 0.9, True, None)
    clicks, moves = [], []
    m.clicked.connect(lambda: clicks.append(1))
    m.moved.connect(lambda x, y: moves.append((x, y)))

    def ev(kind, local, glob):
        return QMouseEvent(kind, QPointF(local), QPointF(glob), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    start = m.pos() + QPoint(30, 30)
    m.mousePressEvent(ev(QEvent.MouseButtonPress, QPoint(30, 30), start))
    m.mouseReleaseEvent(ev(QEvent.MouseButtonRelease, QPoint(30, 30), start))
    assert clicks == [1] and moves == []
    before = m.pos()
    m.mousePressEvent(ev(QEvent.MouseButtonPress, QPoint(30, 30), start))
    m.mouseMoveEvent(ev(QEvent.MouseMove, QPoint(10, 30), start - QPoint(20, 0)))
    m.mouseReleaseEvent(ev(QEvent.MouseButtonRelease, QPoint(10, 30), start - QPoint(20, 0)))
    assert clicks == [1] and len(moves) == 1 and m.pos() != before  # a drag is not a click
    m.hide()


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
