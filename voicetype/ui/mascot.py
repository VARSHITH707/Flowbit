"""The Flowbit mascot: a small floating microphone buddy near the bottom of the screen.

- Click it to start or stop a recording (same as the toggle shortcut); drag it anywhere; right-click for a menu.
- It never takes keyboard focus (WS_EX_NOACTIVATE), so the app you are typing in keeps the cursor. It is not
  click-through: only its fully transparent pixels let clicks pass.
- What it shows is real: the sound waves follow the live microphone level, and every state comes from the
  dictation controller. Idle: dim, gently floating. Recording: bright orange, waves. Transcribing/inserting:
  orange progress ring. Done: happy face and a check. Error: worried face and a "!" badge.
- Reduced motion: no idle floating or blinking; recording still shows your voice level.
Drawn with vector shapes in code (no image files, nothing loaded from the internet).
"""
import ctypes
import math
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QMenu, QWidget

from ..dictation import ACTIVE, DONE, FAILED, IDLE, INSERTING, PROCESSING, RECORDING

GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = -20, 0x08000000, 0x80
ORANGE, BLACK, WHITE, BODY, EDGE = QColor("#FF7900"), QColor("#0B0B0B"), QColor("#F5F5F5"), QColor("#171717"), QColor("#2e2e2e")
MASCOT = 60  # logical px for the mascot square
BUBBLE_H, GAP, DRAG_PX = 28, 4, 4
ACTIVE_MS, IDLE_MS = 33, 66  # 30 fps while working, 15 fps for the gentle idle float


def _pen(color, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def wave_strength(state: str, level: float) -> float:
    """How strongly the sound waves show (0-1). Only while recording, and only as loud as the microphone."""
    return min(1.0, 0.15 + level * 6) if state == RECORDING else 0.0


def bob_offset(state: str, t: float, reduced: bool) -> float:
    """Idle float in px. Still when reduced motion is on or while working (so it never looks busy when idle)."""
    return 0.0 if reduced or state != IDLE else 1.6 * math.sin(t * 1.7)


def paint_mascot(p: QPainter, x: float, y: float, size: float, state: str, t: float, level: float = 0.0,
                 reduced: bool = False) -> None:
    """Draw the mascot into the square (x, y, size). Pure drawing: usable for the window, tray and app icons."""
    u = size / 56.0
    p.save()
    p.translate(x, y + bob_offset(state, t, reduced) * u)
    p.setRenderHint(QPainter.Antialiasing)
    active = state in ACTIVE
    accent = QColor(ORANGE)
    if state == IDLE:
        accent.setAlpha(110)
    cx, cy = 28 * u, 24 * u
    # glow behind the body: bright while recording (pulses with the voice), soft while working
    if state == RECORDING or state in (PROCESSING, INSERTING):
        g = QRadialGradient(QPointF(cx, cy), 27 * u)
        a = int(70 + 120 * wave_strength(state, level)) if state == RECORDING else 70
        c0 = QColor(ORANGE)
        c0.setAlpha(a)
        c1 = QColor(ORANGE)
        c1.setAlpha(0)
        g.setColorAt(0.0, c0)
        g.setColorAt(1.0, c1)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(cx, cy), 27 * u, 27 * u)
    # stand
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#3a3a3a"))
    p.drawRect(QRectF(26.8 * u, 43 * u, 2.4 * u, 7 * u))
    p.drawRoundedRect(QRectF(19 * u, 49.5 * u, 18 * u, 3.6 * u), 1.8 * u, 1.8 * u)
    # body: a rounded microphone head
    p.setBrush(BODY)
    p.setPen(QPen(ORANGE if active else EDGE, (2.2 if active else 1.4) * u))
    p.drawRoundedRect(QRectF(10 * u, 4 * u, 36 * u, 40 * u), 17 * u, 17 * u)
    # grille
    p.setPen(_pen(accent if active else QColor("#303030"), 1.3 * u))
    for i, w in enumerate((10, 14, 10)):
        yy = (10 + i * 3.2) * u
        p.drawLine(QPointF(cx - w / 2 * u, yy), QPointF(cx + w / 2 * u, yy))
    # cheeks
    blush = QColor(ORANGE)
    blush.setAlpha(150 if active or state == DONE else 70)
    p.setPen(Qt.NoPen)
    p.setBrush(blush)
    for bx in (17.5, 38.5):
        p.drawEllipse(QPointF(bx * u, 31.5 * u), 2.4 * u, 1.6 * u)
    _face(p, u, state, t, level, reduced)
    if state == RECORDING:
        _waves(p, u, cx, cy, t, level)
    elif state in (PROCESSING, INSERTING):
        _spinner(p, u, cx, cy, t, reduced)
    elif state == DONE:
        _badge(p, u, ORANGE, "check")
    elif state == FAILED:
        _badge(p, u, QColor("#ffb547"), "!")
    p.restore()


def _face(p: QPainter, u: float, state: str, t: float, level: float, reduced: bool) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(WHITE if state != IDLE else QColor("#d9d9d9"))
    look = 2.0 * math.sin(t * 3.2) if state in (PROCESSING, INSERTING) and not reduced else 0.0
    blink = state == IDLE and not reduced and (t % 4.2) < 0.13
    if state == DONE:  # happy ^ ^
        p.setPen(_pen(WHITE, 1.8 * u))
        p.setBrush(Qt.NoBrush)
        for ex in (22, 34):
            path = QPainterPath(QPointF((ex - 3) * u, 25 * u))
            path.quadTo(QPointF(ex * u, 20.5 * u), QPointF((ex + 3) * u, 25 * u))
            p.drawPath(path)
    else:
        h = 1.2 if blink else (7.5 if state == RECORDING else 6.5)
        w = 4.6 if state != FAILED else 4.0
        for ex in (22, 34):
            p.drawRoundedRect(QRectF((ex - w / 2 + look) * u, (24 - h / 2) * u, w * u, h * u), w / 2 * u, w / 2 * u)
    # mouth
    if state == RECORDING:  # opens with the voice
        open_h = 1.8 + min(1.0, level * 6) * 4.5
        p.setPen(Qt.NoPen)
        p.setBrush(ORANGE)
        p.drawRoundedRect(QRectF(25.2 * u, (34 - open_h / 2) * u, 5.6 * u, open_h * u), 2.6 * u, 2.6 * u)
        return
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(WHITE if state != IDLE else QColor("#bdbdbd"), 1.6 * u))
    if state == FAILED:
        p.drawLine(QPointF(25 * u, 35 * u), QPointF(31 * u, 34 * u))
        return
    depth = 4.2 if state == DONE else 2.6
    path = QPainterPath(QPointF(24 * u, 33 * u))
    path.quadTo(QPointF(28 * u, (33 + depth) * u), QPointF(32 * u, 33 * u))
    p.drawPath(path)


def _waves(p: QPainter, u: float, cx: float, cy: float, t: float, level: float) -> None:
    s = wave_strength(RECORDING, level)
    for i, r in enumerate((24, 29)):
        c = QColor(ORANGE)
        c.setAlpha(int(255 * s * (1.0 if i == 0 else 0.6) * (0.75 + 0.25 * math.sin(t * 9 + i))))
        p.setPen(_pen(c, 2.2 * u))
        p.setBrush(Qt.NoBrush)
        span = 50 + 25 * s
        rect = QRectF(cx - r * u, cy - r * u, 2 * r * u, 2 * r * u)
        p.drawArc(rect, int(-span / 2 * 16), int(span * 16))  # right side
        p.drawArc(rect, int((180 - span / 2) * 16), int(span * 16))  # left side


def _spinner(p: QPainter, u: float, cx: float, cy: float, t: float, reduced: bool) -> None:
    c = QColor(ORANGE)
    c.setAlpha(220)
    p.setPen(_pen(c, 2.2 * u))
    p.setBrush(Qt.NoBrush)
    start = 0 if reduced else -(t * 300) % 360
    p.drawArc(QRectF(cx - 25 * u, cy - 25 * u, 50 * u, 50 * u), int(start * 16), int(80 * 16))


def _badge(p: QPainter, u: float, color: QColor, kind: str) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    center = QPointF(44 * u, 8 * u)
    p.drawEllipse(center, 6 * u, 6 * u)
    p.setPen(_pen(BLACK, 1.8 * u))
    if kind == "check":
        path = QPainterPath(QPointF(41 * u, 8 * u))
        path.lineTo(QPointF(43.3 * u, 10.3 * u))
        path.lineTo(QPointF(47 * u, 5.8 * u))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
    else:
        p.drawLine(QPointF(44 * u, 4.8 * u), QPointF(44 * u, 8.8 * u))
        p.drawPoint(QPointF(44 * u, 11.2 * u))


def mascot_icon(size: int = 64, state: str = DONE) -> QIcon:
    """App / tray icon: the mascot on transparent background."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    paint_mascot(p, 0, 0, size, state, 0.0, reduced=True)
    p.end()
    return QIcon(pm)


def status_text(state: str, detail: str, started: float, mode: str) -> str:
    """The small speech bubble next to the mascot (empty when idle). Says that everything runs on this PC."""
    if state == RECORDING:
        s = int(time.time() - started)
        how = {"hold": "hold", "toggle": "click or press again to stop"}.get(mode, "")
        return f"Listening {s // 60}:{s % 60:02d}" + (f" · {how}" if how else "") + " · on this PC"
    if state == PROCESSING:
        return "Transcribing on this PC"
    if state == INSERTING:
        return "Inserting"
    if state == DONE:
        return (detail.splitlines()[0][:70] if detail else "Done")
    if state == FAILED:
        return (detail.splitlines()[0][:70] if detail else "Something went wrong")
    return ""


class Mascot(QWidget):
    clicked = Signal()
    moved = Signal(int, int)  # new top-left of the mascot (saved in settings)

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip("Flowbit: click to start or stop dictation, drag to move, right-click for options")
        self.state, self.detail, self.mode, self._t0 = IDLE, "", "", 0.0
        self.show_when_idle, self.reduced, self.idle_opacity = True, False, 0.9
        self.level_source = lambda: 0.0
        self.menu_actions: list[tuple[str, object]] = []  # (label, callback) for the right-click menu
        self.anchor: QPoint | None = None  # top-left of the mascot itself; None = bottom centre
        self._press: QPoint | None = None
        self._press_anchor: QPoint | None = None
        self._dragging = False
        self._bubble_left = False
        self._styled = False
        self._frame = QTimer(self, timeout=self.update)
        self._hide = QTimer(self, singleShot=True, timeout=lambda: self.set_state(IDLE))
        self.setFont(QFont("Segoe UI", 9))
        self._relayout()

    # ---------------------------------------------------------------- state
    @property
    def animating(self) -> bool:
        return self._frame.isActive()

    @property
    def frame_ms(self) -> int:
        return self._frame.interval() if self._frame.isActive() else 0

    def set_state(self, state: str, detail: str = "", mode: str = "") -> None:
        self.state, self.detail = state, detail
        if mode:
            self.mode = mode
        self._hide.stop()
        if state == RECORDING:
            self._t0 = time.time()
        if state in (DONE, FAILED):
            self._hide.start(5000 if state == FAILED or detail else 1600)
        self._update_timer()
        self.setWindowOpacity(1.0 if state != IDLE else self.idle_opacity)
        self._relayout()
        if state == IDLE and not self.show_when_idle:
            self.hide()
        else:
            self._show_inactive()
        self.update()

    def configure(self, visible: bool, opacity: float, reduced: bool, pos: list | None) -> None:
        self.show_when_idle, self.idle_opacity, self.reduced = visible, opacity, reduced
        self.anchor = QPoint(*pos) if pos else None
        self.set_state(self.state, self.detail)

    def _update_timer(self) -> None:
        if self.state in ACTIVE or self.state in (DONE, FAILED):
            self._frame.start(ACTIVE_MS)
        elif self.state == IDLE and not self.reduced and self.show_when_idle:
            self._frame.start(IDLE_MS)
        else:
            self._frame.stop()

    # ---------------------------------------------------------------- geometry
    def _text(self) -> str:
        return status_text(self.state, self.detail, self._t0, self.mode)

    def _bubble_w(self) -> int:
        t = self._text()
        return QFontMetrics(self.font()).horizontalAdvance(t) + 26 if t else 0

    def _screen_rect(self, pt: QPoint):
        scr = QGuiApplication.screenAt(pt) or QGuiApplication.primaryScreen()
        return scr.availableGeometry()  # excludes the taskbar

    def _default_anchor(self) -> QPoint:
        g = QGuiApplication.primaryScreen().availableGeometry()
        return QPoint(g.center().x() - MASCOT // 2, g.bottom() - MASCOT - 10)

    def clamp(self, pt: QPoint) -> QPoint:
        """Keep the whole mascot on the screen it is on (any monitor, any scaling), above the taskbar."""
        g = self._screen_rect(pt + QPoint(MASCOT // 2, MASCOT // 2))
        return QPoint(min(max(pt.x(), g.left()), g.right() - MASCOT + 1), min(max(pt.y(), g.top()), g.bottom() - MASCOT + 1))

    def _relayout(self) -> None:
        a = self.clamp(self.anchor or self._default_anchor())
        bw = self._bubble_w()
        g = self._screen_rect(a + QPoint(MASCOT // 2, MASCOT // 2))
        self._bubble_left = bw and a.x() + MASCOT + GAP + bw > g.right()
        self.resize(MASCOT + (GAP + bw if bw else 0), MASCOT)
        self.move(a.x() - (GAP + bw if self._bubble_left else 0), a.y())

    def _mascot_x(self) -> int:
        return self.width() - MASCOT if self._bubble_left else 0

    # ---------------------------------------------------------------- window
    def _show_inactive(self) -> None:
        self.show()
        if not self._styled:  # never take focus, but keep receiving mouse clicks (no WS_EX_TRANSPARENT)
            hwnd = int(self.winId())
            u = ctypes.windll.user32
            u.GetWindowLongW.restype = ctypes.c_long
            u.SetWindowLongW(hwnd, GWL_EXSTYLE, u.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
            self._styled = True

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        level = self.level_source() if self.state == RECORDING else 0.0
        paint_mascot(p, self._mascot_x() + 2, 2, MASCOT - 4, self.state, time.time(), level, self.reduced)
        text = self._text()
        if text:
            bx = 0 if self._bubble_left else MASCOT + GAP
            r = QRectF(bx, (MASCOT - BUBBLE_H) / 2, self.width() - MASCOT - GAP, BUBBLE_H)
            p.setPen(QPen(ORANGE if self.state == RECORDING else EDGE, 1))
            p.setBrush(QColor(11, 11, 11, 235))
            p.drawRoundedRect(r, BUBBLE_H / 2, BUBBLE_H / 2)
            p.setPen(WHITE)
            p.drawText(r.adjusted(13, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft, text)

    # ---------------------------------------------------------------- mouse: click, drag, menu
    def _on_mascot(self, pos: QPoint) -> bool:
        return self._mascot_x() <= pos.x() < self._mascot_x() + MASCOT

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = e.globalPosition().toPoint()
            self._press_anchor = self.clamp(self.anchor or self._default_anchor())
            self._dragging = False
        elif e.button() == Qt.RightButton and self.menu_actions:
            menu = QMenu()
            for label, fn in self.menu_actions:
                menu.addAction(label, fn)
            menu.exec(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self._press is None:
            return
        delta = e.globalPosition().toPoint() - self._press
        if not self._dragging and delta.manhattanLength() >= DRAG_PX:
            self._dragging = True
        if self._dragging:
            self.anchor = self.clamp(self._press_anchor + delta)
            self._relayout()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._press is None:
            return
        self._press = None
        if self._dragging:
            self._dragging = False
            self.moved.emit(self.anchor.x(), self.anchor.y())
        elif self._on_mascot(e.position().toPoint()):
            self.clicked.emit()
