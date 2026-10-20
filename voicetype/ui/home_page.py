from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from ..dictation import DONE, FAILED, IDLE, PROCESSING, RECORDING

STATE_TEXT = {IDLE: "Ready", RECORDING: "Listening...", PROCESSING: "Transcribing...", DONE: "Done", FAILED: "Something went wrong"}


def classify(detail: str) -> tuple[str, str | None, str | None]:
    """error text -> (what to do, button label, action key)."""
    d = detail.lower()
    if "not downloaded" in d:
        return "Download the model once, then dictation works offline.", "Open Models", "models"
    if "microphone" in d or "audio device" in d or "invalid input device" in d:
        return "Check that a microphone is connected and not blocked in Windows privacy settings, then choose it in Settings.", "Open Settings", "settings"
    if "out of memory" in d or "cuda" in d or "gpu" in d:
        return "The GPU ran out of memory or is unavailable. Pick a smaller model or choose CPU in Settings.", "Open Settings", "settings"
    if "no speech" in d or "no audio" in d or "silent" in d:
        return "Nothing was heard. Speak closer to the microphone and try again.", "Try again", "retry"
    return "Try again. If it keeps happening, check the log file in the data folder.", "Try again", "retry"


class HomePage(QWidget):
    open_tab = Signal(str)
    toggle_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, cfg_holder):
        super().__init__()
        self.h = cfg_holder
        self.title = QLabel("VoiceType", objectName="title")
        self.status = QLabel(STATE_TEXT[IDLE], objectName="title")
        self.info = QLabel("", objectName="muted")
        self.info.setWordWrap(True)
        self.notice = QLabel("", objectName="muted")
        self.notice.setWordWrap(True)
        self.go = QPushButton("Start dictation", objectName="primary")
        self.cancel = QPushButton("Cancel")
        self.go.clicked.connect(self.toggle_requested)
        self.cancel.clicked.connect(self.cancel_requested)
        self.err_msg, self.err_hint = QLabel("", objectName="error"), QLabel("")
        self.err_msg.setWordWrap(True)
        self.err_hint.setWordWrap(True)
        self.err_btn = QPushButton("")
        self.err_btn.clicked.connect(self._error_action)
        self._action = None
        self.err_card = QFrame(objectName="errorcard")
        el = QVBoxLayout(self.err_card)
        el.addWidget(self.err_msg)
        el.addWidget(self.err_hint)
        el.addWidget(self.err_btn)
        self.err_card.hide()
        self.text = QTextEdit(readOnly=True, placeholderText="Your last transcript appears here.")
        self.text.setAccessibleName("Last transcript")
        self.copy = QPushButton("Copy transcript")
        self.copy.clicked.connect(lambda: QApplication.clipboard().setText(self.text.toPlainText()))
        self.undo = QPushButton("Undo AI edit (copy original)")
        self.undo.setToolTip("Show and copy exactly what was recognised, before the AI cleaned it up")
        self.undo.clicked.connect(self.undo_ai_edit)
        self.undo.setEnabled(False)
        self._raw = ""
        top = QHBoxLayout()
        top.addWidget(self.go)
        top.addWidget(self.cancel)
        top.addStretch()
        lay = QVBoxLayout(self)
        for w in (self.title, self.status, self.info, self.notice):
            lay.addWidget(w)
        lay.addLayout(top)
        lay.addWidget(self.err_card)
        lay.addWidget(self.text, 1)
        bottom = QHBoxLayout()
        bottom.addWidget(self.copy)
        bottom.addWidget(self.undo)
        lay.addLayout(bottom)
        self.refresh_info()
        self.on_state(IDLE)

    def refresh_info(self, device: str = ""):
        c = self.h.cfg
        hk = c.hotkeys
        keys = {"both": f"hold {hk['hold']}  or  press {hk['toggle']}", "hold": f"hold {hk['hold']}", "toggle": f"press {hk['toggle']}"}[c.recording_mode]
        self.info.setText(f"Dictate: {keys}.  Cancel: {hk['cancel']}.  Model: {c.model}" + (f" on {device}" if device else "") + ".")

    def on_state(self, state: str, detail: str = ""):
        self.status.setText(STATE_TEXT[state])
        self.go.setText("Stop" if state == RECORDING else "Start dictation")
        self.go.setEnabled(state != PROCESSING)
        self.cancel.setEnabled(state in (RECORDING, PROCESSING))
        if state == FAILED:
            hint, label, action = classify(detail)
            self.err_msg.setText(detail)
            self.err_hint.setText(hint)
            self._action = action
            self.err_btn.setText(label or "")
            self.err_btn.setVisible(bool(label))
            self.err_card.show()
        elif state in (RECORDING, PROCESSING):
            self.err_card.hide()
        self.notice.setText(detail if state in (DONE, IDLE) and detail else self.notice.text() if state == PROCESSING else "")

    def set_transcript(self, text: str, raw: str = ""):
        self.text.setPlainText(text)
        self._raw = raw
        self.undo.setEnabled(bool(raw) and raw.strip() != text.strip())

    def undo_ai_edit(self):
        """Like Wispr's 'Undo AI edit': the original is put on the clipboard; press Ctrl+V where you want it."""
        QApplication.clipboard().setText(self._raw)
        self.text.setPlainText(self._raw)
        self.undo.setEnabled(False)
        self.notice.setText("Original transcript copied. Select the AI text in your app and press Ctrl+V to replace it.")

    def _error_action(self):
        if self._action == "retry":
            self.err_card.hide()
            self.toggle_requested.emit()
        elif self._action:
            self.open_tab.emit(self._action)
