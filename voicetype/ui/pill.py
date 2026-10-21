"""Small always-on-top indicator at the bottom of the screen. Never takes keyboard focus.

Idle: a small grey logo (5 sound bars) that stays still. Recording: the logo turns red and its bars bounce with
your live microphone level, plus a gentle wave so it visibly moves even while you pause. Transcribing: an amber
wave. If it is not moving, VoiceType is not recording.
"""
import ctypes
import math
import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

from ..dictation import DONE, FAILED, IDLE, PROCESSING, RECORDING

GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TRANSPARENT = -20, 0x08000000, 0x80, 0x20
LABELS = {IDLE: "", RECORDING: "Listening", PROCESSING: "Transcribing", DONE: "Done", FAILED: "Failed"}
COLORS = {IDLE: "#9aa3ae", RECORDING: "#ff4d4d", PROCESSING: "#f5b942", DONE: "#3ecf8e", FAILED: "#ff6b6b"}
IDLE_BARS = (0.35, 0.6, 0.9, 0.6, 0.35)  # the still logo
LOGO_W, HEIGHT, FRAME_MS = 44, 30, 33
ANIMATED = (RECORDING, PROCESSING)


def bar_heights(state: str, t: float, level: float) -> list[float]:
    """Bar heights 0-1 for the logo at time t. Still when idle; moving while recording or transcribing."""
    if state == RECORDING:
        amp = 0.25 + 0.75 * min(1.0, level * 6)  # louder voice, taller bars
        return [0.2 + 0.8 * amp * (0.5 + 0.5 * math.sin(t * 11 + i * 1.4)) for i in range(5)]
    if state == PROCESSING:
        return [0.25 + 0.5 * (0.5 + 0.5 * math.sin(t * 6 - i * 0.9)) for i in range(5)]
    return list(IDLE_BARS)


class StatePill(QWidget):
    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.state, self.detail, self._t0 = IDLE, "", 0.0
        self.show_when_idle = True
        self.level_source = lambda: 0.0  # set by the app: live mic level while recording
        self._frame = QTimer(self, interval=FRAME_MS, timeout=self.update)  # runs only while animating
        self._hide = QTimer(self, singleShot=True, timeout=self._after_flash)
        self.resize(LOGO_W, HEIGHT)

    # state
    def set_state(self, state: str, detail: str = "") -> None:
        self.state, self.detail = state, detail
        self._hide.stop()
        if state == RECORDING:
            self._t0 = time.time()
        if state in ANIMATED:
            self._frame.start()
        else:
            self._frame.stop()
        if state in (DONE, FAILED):
            self._hide.start(5000 if state == FAILED else 1500)
        self._relayout()
        if state == IDLE and not self.show_when_idle:
            self.hide()
        else:
            self._show_inactive()
        self.update()

    @property
    def animating(self) -> bool:
        return self._frame.isActive()

    def _after_flash(self) -> None:
        self.set_state(IDLE)

    def _text(self) -> str:
        t = LABELS[self.state]
        if self.state == RECORDING:
            s = int(time.time() - self._t0)
            t += f"  {s // 60}:{s % 60:02d}"
        elif self.state == FAILED and self.detail:
            t = self.detail.splitlines()[0][:48]
        return t

    def _relayout(self) -> None:
        text = self._text()
        w = LOGO_W if not text else LOGO_W + self.fontMetrics().horizontalAdvance(text) + 22
        self.resize(min(w, 420), HEIGHT)
        scr = QGuiApplication.primaryScreen().availableGeometry()
        self.move(scr.center().x() - self.width() // 2, scr.bottom() - self.height() - 14)

    def _show_inactive(self) -> None:
        was_hidden = not self.isVisible()
        self.show()
        if was_hidden:  # make the native window non-activating + click-through so it can never grab focus
            hwnd = int(self.winId())
            u = ctypes.windll.user32
            u.GetWindowLongW.restype = ctypes.c_long
            style = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
            u.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        idle = self.state == IDLE
        p.setBrush(QColor(20, 22, 27, 170 if idle else 235))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), HEIGHT / 2, HEIGHT / 2)
        color = QColor(COLORS[self.state])
        p.setBrush(color)
        level = self.level_source() if self.state == RECORDING else 0.0
        for i, h in enumerate(bar_heights(self.state, time.time(), level)):
            bh = max(3.0, h * (HEIGHT - 12))
            p.drawRoundedRect(QRectF(11 + i * 5, (HEIGHT - bh) / 2, 3, bh), 1.5, 1.5)
        text = self._text()
        if text:
            p.setPen(QColor(255, 255, 255))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(QRectF(LOGO_W - 4, 0, self.width() - LOGO_W, self.height()), Qt.AlignVCenter | Qt.AlignLeft, text)
