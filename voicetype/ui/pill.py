"""Small always-on-top state indicator. Must never take keyboard focus from the app being dictated into."""
import ctypes
import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

from ..dictation import DONE, FAILED, IDLE, PROCESSING, RECORDING

GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TRANSPARENT = -20, 0x08000000, 0x80, 0x20
LABELS = {IDLE: "Ready", RECORDING: "Listening", PROCESSING: "Transcribing", DONE: "Done", FAILED: "Failed"}
DOTS = {IDLE: "#7a828e", RECORDING: "#ff4d4d", PROCESSING: "#f5b942", DONE: "#3ecf8e", FAILED: "#ff6b6b"}


class StatePill(QWidget):
    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.state, self.detail, self._t0 = IDLE, "", 0.0
        self.show_when_idle = True
        self._tick = QTimer(self, interval=250, timeout=self.update)
        self._hide = QTimer(self, singleShot=True, timeout=self._after_flash)
        self.resize(190, 34)

    # state
    def set_state(self, state: str, detail: str = "") -> None:
        self.state, self.detail = state, detail
        self._hide.stop()
        if state == RECORDING:
            self._t0 = time.time()
            self._tick.start()
        else:
            self._tick.stop()
        if state in (DONE, FAILED):
            self._hide.start(5000 if state == FAILED else 1500)
        self._relayout()
        if state == IDLE and not self.show_when_idle:
            self.hide()
        else:
            self._show_inactive()
        self.update()

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
        w = max(120, self.fontMetrics().horizontalAdvance(self._text()) + 54)
        self.resize(min(w, 420), 34)
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
        p.setBrush(QColor(20, 22, 27, 150 if idle else 235))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 17, 17)
        p.setBrush(QColor(DOTS[self.state]))
        p.drawEllipse(14, 12, 10, 10)
        p.setPen(QColor(255, 255, 255, 170 if idle else 255))
        f = QFont("Segoe UI", 9)
        p.setFont(f)
        p.drawText(QRectF(32, 0, self.width() - 40, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self._text())
