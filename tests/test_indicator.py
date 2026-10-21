"""The Flowbit mascot: shows the real state, never moves by itself, blinks gently, never takes focus or swallows clicks."""
from PySide6.QtCore import QPoint
from PySide6.QtGui import QGuiApplication, QImage, QPainter

from voicetype.dictation import DONE, FAILED, IDLE, INSERTING, PROCESSING, RECORDING, Dictation, Settings
from voicetype.ui import mascot as mascot_mod
from voicetype.ui.brand import mascot_eyes
from voicetype.ui.mascot import BLINK_S, WIN_H, WIN_W, Mascot, blink_closed, mascot_icon, paint_mascot, status_text, wave_strength


def render(state, t=0.0, level=0.0, reduced=False, closed=0.0) -> bytes:
    img = QImage(60, 60, QImage.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    paint_mascot(p, 0, 0, 60, state, t, level, reduced, closed)
    p.end()
    return bytes(img.constBits())


def test_sound_waves_follow_the_microphone_only_while_recording(qapp):
    assert wave_strength(IDLE, 0.5) == wave_strength(PROCESSING, 0.5) == 0.0
    assert wave_strength(RECORDING, 0.2) > wave_strength(RECORDING, 0.0) > 0  # visible even in a pause
    assert render(RECORDING, level=0.0) != render(RECORDING, level=0.3)  # louder voice looks different


def test_reduced_motion_keeps_the_frame_still(qapp):
    assert render(IDLE, 0.3, reduced=True) == render(IDLE, 2.9, reduced=True)  # no float, no ring spin
    assert render(IDLE, 0.3, closed=0.8) != render(IDLE, 0.3)  # a blink is drawn when the animation is on


def test_every_state_draws_differently(qapp):
    frames = {s: render(s, 1.0, 0.1) for s in (IDLE, RECORDING, PROCESSING, DONE, FAILED)}
    assert len(set(frames.values())) == 5
    assert not mascot_icon(32).isNull()


def test_blink_is_short_smooth_and_rare_enough(qapp):
    assert blink_closed(-0.1) == 0.0 and blink_closed(BLINK_S) == 0.0  # eyes open between blinks
    assert abs(blink_closed(BLINK_S / 2) - 1.0) < 1e-9  # fully shut in the middle
    assert 0 < blink_closed(BLINK_S / 4) < 1  # closes smoothly, not in steps
    assert mascot_mod.BLINK_GAP_S[0] >= 3.0  # never more often than every few seconds


def test_the_ghost_has_two_eyes_to_blink(qapp):
    eyes = mascot_eyes()
    assert len(eyes) == 2
    for x0, y0, x1, y1 in eyes:
        assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1


def test_status_bubble_says_what_is_happening_and_that_it_is_local():
    assert status_text(IDLE, "", 0, "") == ""
    assert "on this PC" in status_text(RECORDING, "", 0, "toggle") and "click" in status_text(RECORDING, "", 0, "toggle")
    assert status_text(PROCESSING, "", 0, "") == "Transcribing on this PC"
    assert status_text(FAILED, "Microphone unavailable: x\nmore", 0, "") == "Microphone unavailable: x"


def test_window_size_is_fixed_and_state_changes_never_move_it(qapp):
    m = Mascot()
    m.configure(True, 0.9, False, [300, 300])
    start = (m.pos().x(), m.pos().y())
    assert (m.width(), m.height()) == (WIN_W, WIN_H)
    for state, detail in ((RECORDING, ""), (PROCESSING, ""), (INSERTING, ""), (DONE, "a much longer result text that makes the bubble wide"),
                          (FAILED, "Microphone unavailable: test"), (IDLE, "")):
        m.set_state(state, detail, "toggle")
        assert (m.pos().x(), m.pos().y()) == start, state  # the bubble's width never moves the window
        assert (m.width(), m.height()) == (WIN_W, WIN_H)
    m.hide()


def test_bubble_side_flips_only_at_placement_not_per_state(qapp):
    m = Mascot()
    g = QGuiApplication.primaryScreen().availableGeometry()
    m.configure(True, 0.9, False, [g.right() - 80, g.top() + 100])  # near the right edge: bubble goes left
    left_side = m._bubble_left
    m.set_state(RECORDING, mode="hold")
    m.set_state(IDLE)
    assert m._bubble_left == left_side  # not flipped by the state change
    m.hide()


def test_only_the_mascot_and_its_bubble_take_clicks(qapp):
    from PySide6.QtCore import QPoint as P
    m = Mascot()
    m.configure(True, 0.9, False, [300, 300])
    m.set_state(IDLE)
    assert m.mask().contains(P(m._mascot_x() + 10, 10))
    assert not m.mask().contains(P(WIN_W - 5, 5))  # empty space: clicks go to the app underneath
    m.set_state(RECORDING, mode="hold")
    assert m.mask().contains(P(WIN_W - 60, WIN_H // 2)) or m._bubble_rect() is not None
    m.hide()


def test_animation_timer_matches_state_and_settings(qapp):
    m = Mascot()
    m.configure(visible=True, opacity=0.8, reduced=False, pos=None)
    assert not m.animating  # idle is still: no per-frame redraw
    m.set_state(RECORDING, mode="hold")
    assert m.animating and m.frame_ms == mascot_mod.ACTIVE_MS and m.windowOpacity() == 1.0
    m.set_state(INSERTING)
    assert m.animating
    m.configure(visible=True, opacity=0.8, reduced=True, pos=None)
    m.set_state(IDLE)
    assert not m.animating and not m._blink.isActive()  # reduced motion: no blink, no animation
    m.configure(visible=False, opacity=0.8, reduced=False, pos=None)
    assert not m.isVisible() and not m.animating  # hidden when idle: costs nothing
    m.hide()


def test_position_is_kept_on_screen(qapp):
    m = Mascot()
    far = m.clamp(QPoint(10**6, 10**6))
    near = m.clamp(QPoint(-10**6, -10**6))
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
    start = m.pos() + QPoint(m._mascot_x() + 30, 30)
    m.mousePressEvent(ev(QEvent.MouseButtonPress, QPoint(m._mascot_x() + 30, 30), start))
    m.mouseReleaseEvent(ev(QEvent.MouseButtonRelease, QPoint(m._mascot_x() + 30, 30), start))
    assert clicks == [1] and moves == []  # a plain click starts or stops dictation, and does not move it
    before = m.pos()
    m.mousePressEvent(ev(QEvent.MouseButtonPress, QPoint(m._mascot_x() + 30, 30), start))
    m.mouseMoveEvent(ev(QEvent.MouseMove, QPoint(m._mascot_x() + 10, 30), start - QPoint(20, 0)))
    m.mouseReleaseEvent(ev(QEvent.MouseButtonRelease, QPoint(m._mascot_x() + 10, 30), start - QPoint(20, 0)))
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
