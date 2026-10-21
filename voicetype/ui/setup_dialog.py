"""First-run setup: microphone test, model download, hotkeys."""
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from .. import models
from ..audio import MicError, list_inputs, record
from .settings_page import combo
from .workers import Job, with_progress

INTRO = ("Flowbit turns your speech into text in any app. Everything runs on this PC: no account, no subscription, "
         "no word limit, and your audio is never uploaded.\n\nThis takes about two minutes: pick a microphone, "
         "download a speech model once, and you are ready.")


class SetupDialog(QDialog):
    def __init__(self, cfg_holder, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Flowbit")
        self.setMinimumWidth(520)
        self.h, self._job = cfg_holder, None
        self.pages = QStackedWidget()
        self._welcome_page()
        self._mic_page(self.h.cfg)
        self._model_page(self.h.cfg)
        self._hotkeys_page(self.h.cfg)
        self.back, self.next = QPushButton("Back"), QPushButton("Next", objectName="primary")
        self.back.clicked.connect(lambda: self._go(-1))
        self.next.clicked.connect(lambda: self._go(1))
        nav = QHBoxLayout()
        nav.addStretch()
        nav.addWidget(self.back)
        nav.addWidget(self.next)
        lay = QVBoxLayout(self)
        lay.addWidget(self.pages)
        lay.addLayout(nav)
        self._model_state()
        self._nav()

    def _page(self, title, *widgets):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel(title, objectName="title"))
        for x in widgets:
            lay.addWidget(x)
        lay.addStretch()
        self.pages.addWidget(w)

    def _welcome_page(self):
        intro = QLabel(INTRO)
        intro.setWordWrap(True)
        self._page("Welcome", intro)

    def _mic_page(self, c):
        self.mic = combo([(None, "System default")] + [(i, n) for i, n in list_inputs()], c.mic)
        self.mic_btn = QPushButton("Test microphone (speak for 2 seconds)")
        self.mic_btn.clicked.connect(self.test_mic)
        self.level = QProgressBar(maximum=100)
        self.mic_msg = QLabel("", objectName="muted")
        self.mic_msg.setWordWrap(True)
        self._page("Microphone", self.mic, self.mic_btn, self.level, self.mic_msg)

    def _model_page(self, c):
        self.model = combo([(m, f"{m}  ({s})") for m, s in models.MODELS.items()], c.model)
        self.model.currentIndexChanged.connect(self._model_state)
        self.dl = QPushButton("Download model", objectName="primary")
        self.dl.clicked.connect(self.download)
        self.bar = QProgressBar()
        self.bar.hide()
        self.model_msg = QLabel("", objectName="muted")
        self.model_msg.setWordWrap(True)
        self._page("Speech model", QLabel("large-v3-turbo is the most accurate; small is faster and lighter."),
                   self.model, self.dl, self.bar, self.model_msg)

    def _hotkeys_page(self, c):
        hk = c.hotkeys
        keys = QLabel(f"Hold  {hk['hold']}  and speak, release to insert the text.\n"
                      f"Or press  {hk['toggle']}  to start and again to stop.\n"
                      f"Press  {hk['cancel']}  to cancel.\n\nChange these any time in Settings.")
        keys.setWordWrap(True)
        self._page("Hotkeys", keys)

    def _nav(self):
        i, n = self.pages.currentIndex(), self.pages.count()
        self.back.setEnabled(i > 0)
        self.next.setText("Finish" if i == n - 1 else "Next")

    def _go(self, d):
        i = self.pages.currentIndex() + d
        if i >= self.pages.count():
            c = self.h.cfg
            c.mic, c.model, c.first_run_done = self.mic.currentData(), self.model.currentData(), True
            c.save()
            self.accept()
            return
        self.pages.setCurrentIndex(max(i, 0))
        self._nav()

    def test_mic(self):
        self.mic_btn.setEnabled(False)
        self.mic_msg.setText("Listening...")
        dev = self.mic.currentData()

        def run():
            audio = record(2.0, dev)
            return float(abs(audio).max())
        job = self._job = Job(run)
        job.finished.connect(self._mic_done)
        job.failed.connect(lambda e: self._mic_done(None, e))
        job.start()

    def _mic_done(self, peak, err=None):
        self.mic_btn.setEnabled(True)
        if err or peak is None:
            self.level.setValue(0)
            self.mic_msg.setText(f"Could not open this microphone: {err}. Pick another one or check Windows microphone privacy settings.")
            return
        self.level.setValue(min(100, int(peak * 400)))
        self.mic_msg.setText("Sound detected. This microphone works." if peak > 0.02 else "Very quiet or silent. Speak louder, move closer, or pick another microphone.")

    def _model_state(self):
        ok = models.is_available(self.model.currentData())
        self.dl.setEnabled(not ok and self._job is None)
        self.model_msg.setText("Already downloaded." if ok else "Not downloaded yet (needs internet once).")

    def download(self):
        name = self.model.currentData()
        self.dl.setEnabled(False)
        self.bar.show()
        job = self._job = Job(with_progress(lambda n, cb: models.download(n, cb)), name)
        job.progress.connect(lambda d, t: (self.bar.setMaximum(max(t, 1)), self.bar.setValue(d)))
        job.finished.connect(lambda _: self._dl_done("Downloaded. Dictation now works offline."))
        job.failed.connect(lambda e: self._dl_done(f"Download failed: {e}. Check your connection and try again.", True))
        job.start()

    def _dl_done(self, msg, err=False):
        self._job = None
        self.bar.hide()
        self._model_state()
        self.model_msg.setText(msg)
        if err:
            self.dl.setEnabled(True)
