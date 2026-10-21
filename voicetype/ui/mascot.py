"""The Flowbit mascot: a small ghost-shaped buddy that floats near the bottom of the screen.

- Click it to start or stop a recording (same as the toggle shortcut); drag it anywhere; right-click for a menu.
- The window never changes size or moves by itself. Its position changes only when you drag it, when settings
  change, or when the screen layout changes. Status text and animation never move the window.
- Animation is drawn inside the window: the sound waves follow the live microphone level, a restrained blink
  closes the eyes now and then, and a turning ring shows that work is in progress.
- It never takes keyboard focus (WS_EX_NOACTIVATE). Outside the mascot and its speech bubble the window is
  masked off, so clicks reach the apps underneath.
- Reduced motion: no blinking, no waves or rings; the state is still shown with still marks.
"""
import ctypes
import math
import random
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRegion
from PySide6.QtWidgets import QMenu, QWidget

from ..dictation import ACTIVE, DONE, FAILED, IDLE, INSERTING, PROCESSING, RECORDING
from .brand import mascot_eyes, mascot_pixmap

GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = -20, 0x08000000, 0x80
ORANGE, BLACK, WHITE, BODY, EDGE = QColor("#FF7900"), QColor("#0B0B0B"), QColor("#F5F5F5"), QColor("#171717"), QColor("#2e2e2e")
MASCOT = 60  # logical px for the mascot square
BUBBLE_MAX, BUBBLE_H, GAP, DRAG_PX = 320, 28, 4, 4
WIN_W, WIN_H = MASCOT + GAP + BUBBLE_MAX, MASCOT  # fixed: the window is never resized
ACTIVE_MS = 33  # 30 fps only while working or blinking
BLINK_S = 0.2  # a blink takes this long, closing and opening
BLINK_GAP_S = (3.5, 6.5)  # random pause between blinks, so they never look rhythmic


def _pen(color, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def wave_strength(state: str, level: float) -> float:
    """How strongly the sound waves show (0-1). Only while recording, and only as loud as the microphone."""
    return min(1.0, 0.15 + level * 6) if state == RECORDING else 0.0


def blink_closed(elapsed: float) -> float:
    """How closed the eyes are (0 = open, 1 = shut) at `elapsed` seconds into a blink. Smooth in and out."""
    if elapsed < 0 or elapsed >= BLINK_S:
        return 0.0
    return math.sin(math.pi * elapsed / BLINK_S)


def _sprite_rect(size: float) -> QRectF:
    """The ghost fills most of the square; the outer ring is kept for sound waves and badges."""
    w = size * 0.84
    return QRectF((size - w) / 2, (size - w) / 2, w, w)


def _backdrop(p: QPainter, size: float, state: str) -> None:
    """A dark round badge behind the ghost, so its dark body stays visible on a black or dark-grey desktop."""
    p.setBrush(QColor(44, 44, 44, 170 if state == IDLE else 225))
    p.setPen(_pen(ORANGE, max(1.0, size * 0.03)) if state != IDLE else Qt.NoPen)
    r = size * 0.46
    p.drawEllipse(QPointF(size / 2, size / 2), r, r)


def _draw_sprite(p: QPainter, size: float, opacity: float = 1.0, closed: float = 0.0) -> None:
    """The ghost image, with the eyes closed by `closed` (0-1) when blinking. The eyes are painted over the
    picture's own eyes: a dark lid fades in, and a short orange line shows the shut eye."""
    pm = mascot_pixmap()
    rect = _sprite_rect(size)
    p.setOpacity(opacity)
    if pm is not None:
        p.drawPixmap(rect, pm, QRectF(pm.rect()))
    else:  # image missing: a plain round shape, so something still shows
        p.setPen(QPen(ORANGE, max(1.0, size * 0.04)))
        p.setBrush(BODY)
        p.drawEllipse(rect)
    p.setOpacity(1.0)
    if closed > 0 and pm is not None:
        for x0, y0, x1, y1 in mascot_eyes():
            box = QRectF(rect.x() + x0 * rect.width(), rect.y() + y0 * rect.height(),
                         (x1 - x0) * rect.width(), (y1 - y0) * rect.height())
            lid = QColor(14, 14, 14, int(255 * min(1.0, closed * 1.15)))
            p.setPen(Qt.NoPen)
            p.setBrush(lid)
            p.drawRoundedRect(box.adjusted(-2, -2, 2, 2), box.height() / 2, box.height() / 2)
            if closed > 0.4:  # the shut eye: a short line across the eye
                line = QColor(ORANGE)
                line.setAlpha(int(255 * min(1.0, (closed - 0.4) * 2.5)))
                p.setPen(_pen(line, max(1.5, size * 0.035)))
                cy = box.center().y()
                p.drawLine(QPointF(box.center().x() - box.width() * 0.35, cy), QPointF(box.center().x() + box.width() * 0.35, cy))


def paint_mascot(p: QPainter, x: float, y: float, size: float, state: str, t: float, level: float = 0.0,
                 reduced: bool = False, closed: float = 0.0) -> None:
    """Draw the Flowbit ghost into the square (x, y, size) with its state marks. Idle: dimmed. Recording: full
    colour, sound waves follow your voice. Working: an orange ring turns. Done / error: a check or a '!' badge.
    Pure drawing (no timers): usable for icons, tests and the widget."""
    p.save()
    p.translate(x, y)
    p.setRenderHint(QPainter.Antialiasing)
    _backdrop(p, size, state)
    _draw_sprite(p, size, opacity=0.85 if state == IDLE else 1.0, closed=0.0 if reduced else closed)
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
    """App and tray icon: the Flowbit ghost in full colour on a transparent background."""
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
    moved = Signal(int, int)  # the mascot's new top-left (saved in settings after a drag)

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(WIN_W, WIN_H)
        self.setToolTip("Flowbit: click to start or stop dictation, drag to move, right-click for options")
        self.state, self.detail, self.mode, self._t0 = IDLE, "", "", 0.0
        self.show_when_idle, self.reduced, self.idle_opacity = True, False, 0.9
        self.level_source = lambda: 0.0
        self.menu_actions: list[tuple[str, object]] = []  # (label, callback) for the right-click menu
        self.anchor: QPoint | None = None  # the mascot's own top-left; None = bottom centre of the main screen
        self._bubble_left = False
        self._press: QPoint | None = None
        self._press_window: QPoint | None = None
        self._dragging = False
        self._styled = False
        self._blink_t0: float | None = None
        self._frame = QTimer(self, timeout=self.update)
        self._blink = QTimer(self, singleShot=True, timeout=self._start_blink)
        self._hide = QTimer(self, singleShot=True, timeout=lambda: self.set_state(IDLE))
        self.setFont(QFont("Segoe UI", 9))
        app = QGuiApplication.instance()
        if app is not None:  # re-place the mascot when displays are added or removed
            app.screenAdded.connect(lambda _s: self._place())
            app.screenRemoved.connect(lambda _s: self._place())
        self._place()

    # ---------------------------------------------------------------- state
    @property
    def animating(self) -> bool:
        return self._frame.isActive()

    @property
    def frame_ms(self) -> int:
        return self._frame.interval() if self._frame.isActive() else 0

    def set_state(self, state: str, detail: str = "", mode: str = "") -> None:
        """Change what the mascot shows. This never moves or resizes the window."""
        self.state, self.detail = state, detail
        if mode:
            self.mode = mode
        self._hide.stop()
        if state == RECORDING:
            self._t0 = time.time()
        if state in (DONE, FAILED):
            self._hide.start(5000 if state == FAILED or detail else 1600)
        self.setWindowOpacity(1.0 if state != IDLE else self.idle_opacity)
        self._update_mask()
        if state == IDLE and not self.show_when_idle:
            self.hide()
        else:
            self._show_inactive()
        self._update_timers()
        self.update()

    def configure(self, visible: bool, opacity: float, reduced: bool, pos: list | None) -> None:
        self.show_when_idle, self.idle_opacity, self.reduced = visible, opacity, reduced
        self.anchor = QPoint(*pos) if pos else None
        self._place()
        self.set_state(self.state, self.detail)

    def _update_timers(self) -> None:
        """Animate only when something is happening: working states run at 30 fps; idle blinks now and then."""
        if not self.reduced and (self.state in ACTIVE or self.state in (DONE, FAILED) or self._blink_t0 is not None):
            self._frame.start(ACTIVE_MS)
        else:
            self._frame.stop()
        if self.reduced or not self.isVisible() or self.state not in (IDLE, RECORDING, PROCESSING):
            self._blink.stop()
        elif self._blink_t0 is None and not self._blink.isActive():
            self._blink.start(int(random.uniform(*BLINK_GAP_S) * 1000))

    def _start_blink(self) -> None:
        self._blink_t0 = time.time()
        self._update_timers()

    # ---------------------------------------------------------------- placement (the only place that moves the window)
    def _screen(self, pt: QPoint):
        scr = QGuiApplication.screenAt(pt) or QGuiApplication.primaryScreen()
        return scr.availableGeometry()  # excludes the taskbar

    def _default_anchor(self) -> QPoint:
        g = QGuiApplication.primaryScreen().availableGeometry()
        return QPoint(g.center().x() - MASCOT // 2, g.bottom() - MASCOT - 10)

    def clamp(self, pt: QPoint) -> QPoint:
        """Keep the whole mascot on the screen it is on (any monitor, any scaling), above the taskbar."""
        g = self._screen(pt + QPoint(MASCOT // 2, MASCOT // 2))
        return QPoint(min(max(pt.x(), g.left()), g.right() - MASCOT + 1), min(max(pt.y(), g.top()), g.bottom() - MASCOT + 1))

    def _place(self) -> None:
        """Put the window where the mascot's anchor says. The speech bubble goes left only when there is no room right."""
        a = self.clamp(self.anchor or self._default_anchor())
        g = self._screen(a + QPoint(MASCOT // 2, MASCOT // 2))
        self._bubble_left = a.x() + MASCOT + GAP + BUBBLE_MAX > g.right()
        self.anchor = a
        self.move(self._window_pos(a))

    def _window_pos(self, anchor: QPoint) -> QPoint:
        return QPoint(anchor.x() - (WIN_W - MASCOT if self._bubble_left else 0), anchor.y())

    def _mascot_x(self) -> int:
        return WIN_W - MASCOT if self._bubble_left else 0

    def _bubble_rect(self) -> QRectF | None:
        text = self._text()
        if not text:
            return None
        bw = min(BUBBLE_MAX, QFontMetrics(self.font()).horizontalAdvance(text) + 26)
        bx = self._mascot_x() - GAP - bw if self._bubble_left else self._mascot_x() + MASCOT + GAP
        return QRectF(bx, (MASCOT - BUBBLE_H) / 2, bw, BUBBLE_H)

    def _update_mask(self) -> None:
        """Only the mascot and its visible bubble take clicks; the rest of the window lets them through."""
        region = QRegion(self._mascot_x(), 0, MASCOT, MASCOT)
        b = self._bubble_rect()
        if b is not None:
            region = region.united(QRegion(int(b.x()), int(b.y()), int(b.width()), int(b.height())))
        self.setMask(region)

    # ---------------------------------------------------------------- window
    def _text(self) -> str:
        return status_text(self.state, self.detail, self._t0, self.mode)

    def _show_inactive(self) -> None:
        self.show()
        if not self._styled:  # never take focus, but keep receiving mouse clicks (no WS_EX_TRANSPARENT)
            hwnd = int(self.winId())
            u = ctypes.windll.user32
            u.GetWindowLongW.restype = ctypes.c_long
            u.SetWindowLongW(hwnd, GWL_EXSTYLE, u.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
            self._styled = True

    def paintEvent(self, _):
        now = time.time()
        closed = 0.0
        if self._blink_t0 is not None:
            closed = blink_closed(now - self._blink_t0)
            if now - self._blink_t0 >= BLINK_S:  # the blink is over: open the eyes and wait for the next one
                self._blink_t0 = None
                self._update_timers()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        level = self.level_source() if self.state == RECORDING else 0.0
        paint_mascot(p, self._mascot_x() + 2, 2, MASCOT - 4, self.state, now, level, self.reduced, closed)
        b = self._bubble_rect()
        if b is not None:
            p.setPen(QPen(ORANGE if self.state == RECORDING else EDGE, 1))
            p.setBrush(QColor(11, 11, 11, 235))
            p.drawRoundedRect(b, BUBBLE_H / 2, BUBBLE_H / 2)
            p.setPen(WHITE)
            p.drawText(b.adjusted(13, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft, self._text())

    # ---------------------------------------------------------------- mouse: click, drag, menu
    def _on_mascot(self, pos: QPoint) -> bool:
        return self._mascot_x() <= pos.x() < self._mascot_x() + MASCOT

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = e.globalPosition().toPoint()
            self._press_window = self.pos()
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
        if self._dragging:  # only an intentional drag moves the window
            start_anchor = QPoint(self._press_window.x() + self._mascot_x(), self._press_window.y())
            self.anchor = self.clamp(start_anchor + delta)
            self.move(self._window_pos(self.anchor))

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._press is None:
            return
        self._press = None
        if self._dragging:
            self._dragging = False
            self._place()  # the bubble side is decided again for the new spot
            self.moved.emit(self.anchor.x(), self.anchor.y())
        elif self._on_mascot(e.position().toPoint()):
            self.clicked.emit()
