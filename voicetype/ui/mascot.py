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
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QWidget

from ..dictation import ACTIVE, DONE, FAILED, IDLE, INSERTING, PROCESSING, RECORDING
from .brand import mascot_pixmap

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


def _sprite_rect(size: float) -> QRectF:
    """The character sits in the middle of the square; the outer ring is kept for sound waves and badges."""
    w = size * 0.7
    h = w * 263 / 256  # proportions of the approved mascot image
    return QRectF((size - w) / 2, size * 0.1 + (size * 0.8 - h) / 2, w, h)


def _draw_sprite(p: QPainter, size: float, opacity: float = 1.0) -> None:
    pm = mascot_pixmap()
    p.setOpacity(opacity)
    if pm is not None:
        p.drawPixmap(_sprite_rect(size), pm, QRectF(pm.rect()))
    else:  # image missing: a plain round shape, so something still shows
        p.setPen(QPen(ORANGE, max(1.0, size * 0.04)))
        p.setBrush(BODY)
        p.drawRoundedRect(_sprite_rect(size), size * 0.3, size * 0.3)
    p.setOpacity(1.0)


def paint_mascot(p: QPainter, x: float, y: float, size: float, state: str, t: float, level: float = 0.0,
                 reduced: bool = False) -> None:
    """Draw the approved Flowbit character into the square (x, y, size), with state marks.
    Idle: dimmed and floating gently. Recording: full colour, sound waves follow your voice. Working: an orange
    ring turns. Done / error: a check or a '!' badge. Pure drawing: also used for icons and for the tests."""
    p.save()
    p.translate(x, y + bob_offset(state, t, reduced) * size / 56.0)
    p.setRenderHint(QPainter.Antialiasing)
    _draw_sprite(p, size, opacity=0.45 if state == IDLE else 1.0)
    if state == RECORDING:
        _waves(p, size, t, level)
    elif state in (PROCESSING, INSERTING):
        _spinner(p, size, t, reduced)
    elif state == DONE:
        _badge(p, size, ORANGE, "check")
    elif state == FAILED:
        _badge(p, size, QColor("#ffb547"), "!")
    p.restore()


def _waves(p: QPainter, size: float, t: float, level: float) -> None:
    s = wave_strength(RECORDING, level)
    cx, cy = size / 2, size / 2
    for i, k in enumerate((0.47, 0.5)):
        c = QColor(ORANGE)
        c.setAlpha(int(255 * s * (1.0 if i == 0 else 0.6) * (0.75 + 0.25 * math.sin(t * 9 + i))))
        p.setPen(_pen(c, max(1.5, size * 0.04)))
        p.setBrush(Qt.NoBrush)
        r = size * k
        span = 50 + 25 * s
        rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        p.drawArc(rect, int(-span / 2 * 16), int(span * 16))  # right side
        p.drawArc(rect, int((180 - span / 2) * 16), int(span * 16))  # left side


def _spinner(p: QPainter, size: float, t: float, reduced: bool) -> None:
    c = QColor(ORANGE)
    c.setAlpha(230)
    p.setPen(_pen(c, max(1.5, size * 0.04)))
    p.setBrush(Qt.NoBrush)
    start = 0 if reduced else -(t * 300) % 360
    r = size * 0.47
    p.drawArc(QRectF(size / 2 - r, size / 2 - r, 2 * r, 2 * r), int(start * 16), int(80 * 16))


def _badge(p: QPainter, size: float, color: QColor, kind: str) -> None:
    cx, cy, r = size * 0.84, size * 0.16, size * 0.13
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.setPen(_pen(BLACK, max(1.5, size * 0.05)))
    p.setBrush(Qt.NoBrush)
    if kind == "check":
        path = QPainterPath(QPointF(cx - r * 0.5, cy))
        path.lineTo(QPointF(cx - r * 0.1, cy + r * 0.4))
        path.lineTo(QPointF(cx + r * 0.55, cy - r * 0.4))
        p.drawPath(path)
    else:
        p.drawLine(QPointF(cx, cy - r * 0.55), QPointF(cx, cy + r * 0.15))
        p.drawPoint(QPointF(cx, cy + r * 0.5))


def mascot_icon(size: int = 64) -> QIcon:
    """App and tray icon: the Flowbit character in full colour on a transparent background."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    _draw_sprite(p, size)
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
