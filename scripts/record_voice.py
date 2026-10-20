"""Record your voice dataset for fine-tuning (step 1 of 3: record -> train -> evaluate).

  .\\.venv\\Scripts\\python.exe scripts\\record_voice.py

Read the sentence shown (or say anything you like), press Stop, make the text box match EXACTLY what you said,
then Save. Clips go to userdata\\voice\\ (never uploaded, excluded from git). Aim for 30-60 minutes in total;
you can stop and continue any time.
"""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sounddevice as sd  # noqa: E402
from PySide6.QtCore import QObject, Qt, Signal  # noqa: E402
from PySide6.QtGui import QFont, QKeySequence, QShortcut  # noqa: E402
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,  # noqa: E402
                               QPushButton, QVBoxLayout, QWidget)

from voicetype import voicedata as vd  # noqa: E402
from voicetype.audio import SAMPLE_RATE, Recorder  # noqa: E402
from voicetype.config import Config  # noqa: E402
from voicetype.history import History  # noqa: E402
from voicetype.speech import Engine  # noqa: E402
from voicetype.ui.theme import apply_theme  # noqa: E402
from voicetype.ui.workers import Job  # noqa: E402

GOAL_MINUTES = 60


def load_prompts(done: set[str]) -> list[str]:
    """Built-in sentences plus your own past dictations (your real words), minus what you already recorded."""
    lines = (ROOT / "scripts" / "voice_prompts.txt").read_text(encoding="utf-8").splitlines()
    builtin = [s.strip() for s in lines if s.strip() and not s.startswith("#")]
    try:
        h = History()
        own = [e.text for e in h.list(limit=2000) if 3 <= len(e.text.split()) <= 60]
        h.close()
    except Exception:
        own = []
    random.shuffle(builtin)
    random.shuffle(own)
    seen, out = set(done), []
    for s in [x for pair in zip(builtin, own) for x in pair] + builtin[len(own):] + own[len(builtin):]:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


class _Bridge(QObject):
    limit = Signal()


class Window(QWidget):
    def __init__(self):
        super().__init__()
        cfg = Config.load()
        self.lang = cfg.language or None  # "" means auto-detect
        self.model_name, self.device_idx, self.compute = cfg.model, cfg.mic, cfg.device
        self.engine, self.audio, self.recorder = None, None, None
        self.prompts = load_prompts({e["text"] for e in vd.load()})
        self.bridge = _Bridge()
        self.bridge.limit.connect(self.toggle_record)
        self.setWindowTitle("VoiceType - record your voice")
        self.resize(760, 520)

        big = QFont()
        big.setPointSize(15)
        self.prompt = QLabel(wordWrap=True, textInteractionFlags=Qt.TextSelectableByMouse)
        self.prompt.setFont(big)
        self.status = QLabel(wordWrap=True)
        self.box = QPlainTextEdit(placeholderText="After you stop, what the current model heard appears here. "
                                                  "Fix it so it matches EXACTLY what you said.")
        self.box.setFont(big)
        self.rec_btn = QPushButton("Record  (F5)")
        self.rec_btn.setEnabled(False)
        self.play_btn, self.use_btn = QPushButton("Play back"), QPushButton("I read the sentence above exactly")
        self.save_btn, self.skip_btn = QPushButton("Save  (Ctrl+S)"), QPushButton("Next sentence")
        self.undo_btn = QPushButton("Delete last saved clip")
        self.totals = QLabel()

        row1, row2 = QHBoxLayout(), QHBoxLayout()
        for b in (self.rec_btn, self.play_btn, self.use_btn):
            row1.addWidget(b)
        for b in (self.save_btn, self.skip_btn, self.undo_btn):
            row2.addWidget(b)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Read this out loud (or say anything you normally dictate):"))
        lay.addWidget(self.prompt)
        lay.addLayout(row1)
        lay.addWidget(self.box, 1)
        lay.addLayout(row2)
        lay.addWidget(self.status)
        lay.addWidget(self.totals)

        self.rec_btn.clicked.connect(self.toggle_record)
        self.play_btn.clicked.connect(lambda: self.audio is not None and sd.play(self.audio, SAMPLE_RATE))
        self.use_btn.clicked.connect(lambda: self.box.setPlainText(self.prompt.text()))
        self.save_btn.clicked.connect(self.save)
        self.skip_btn.clicked.connect(self.next_prompt)
        self.undo_btn.clicked.connect(self.undo)
        QShortcut(QKeySequence("F5"), self, self.toggle_record)
        QShortcut(QKeySequence("Ctrl+S"), self, self.save)

        self.next_prompt()
        self.set_clip_buttons(False)
        self.update_totals()
        self.status.setText(f"Loading the speech model ({self.model_name})...")
        self._job = Job(Engine, self.model_name, self.compute, None, True).start()
        self._job.finished.connect(self.engine_ready)
        self._job.failed.connect(lambda m: self.status.setText(f"Could not load the speech model: {m}"))

    def engine_ready(self, engine):
        self.engine = engine
        self.rec_btn.setEnabled(True)
        self.status.setText(f"Ready ({engine.device}). Press Record or F5, speak, then press it again to stop.")

    def set_clip_buttons(self, on: bool):
        for b in (self.play_btn, self.use_btn, self.save_btn):
            b.setEnabled(on)

    def next_prompt(self):
        self.prompt.setText(self.prompts.pop(0) if self.prompts else "You have recorded every sentence. "
                            "Keep going by saying anything you normally dictate.")
        self.box.clear()
        self.audio = None
        self.set_clip_buttons(False)

    def toggle_record(self):
        if self.engine is None:
            return
        if self.recorder is None:
            try:
                self.recorder = Recorder(self.device_idx, max_seconds=vd.MAX_SECONDS, on_limit=self.bridge.limit.emit)
                self.recorder.start()
            except Exception as e:
                self.recorder = None
                self.status.setText(str(e))
                return
            self.rec_btn.setText("Stop  (F5)")
            self.status.setText(f"Recording... speak now (stops by itself after {vd.MAX_SECONDS} s).")
            self.set_clip_buttons(False)
            return
        self.audio, self.recorder = self.recorder.stop(), None
        self.rec_btn.setText("Record  (F5)")
        self.rec_btn.setEnabled(False)
        self.status.setText("Transcribing with the current model...")
        self._tjob = Job(self.engine.transcribe, self.audio, self.lang).start()
        self._tjob.finished.connect(self.heard)
        self._tjob.failed.connect(self.heard_nothing)

    def heard(self, res):
        self.baseline = res.text
        self.box.setPlainText(res.text)
        self.rec_btn.setEnabled(True)
        self.set_clip_buttons(True)
        self.status.setText("Check the text: it must match EXACTLY what you said (fix any mistakes), then Save.")

    def heard_nothing(self, msg):
        self.baseline = ""
        self.rec_btn.setEnabled(True)
        self.set_clip_buttons(self.audio is not None)
        self.status.setText(f"{msg} Type what you said and Save, or record again.")

    def save(self):
        if self.audio is None or not self.save_btn.isEnabled():
            return
        try:
            vd.save(self.audio, self.box.toPlainText(), getattr(self, "baseline", ""),
                    "prompt" if self.box.toPlainText().strip() == self.prompt.text().strip() else "free")
        except ValueError as e:
            QMessageBox.warning(self, "Not saved", str(e))
            return
        self.update_totals()
        self.next_prompt()
        self.status.setText("Saved. Next sentence: press Record or F5.")

    def undo(self):
        e = vd.delete_last()
        self.update_totals()
        self.status.setText(f"Deleted: \"{e['text'][:60]}\"" if e else "Nothing to delete.")

    def update_totals(self):
        es = vd.load()
        mins = sum(e["seconds"] for e in es) / 60
        pairs = [(e["text"], e["baseline"]) for e in es if e.get("baseline")]
        err = f" The current model got {vd.wer(pairs):.1%} of your words wrong so far." if pairs else ""
        self.totals.setText(f"Saved: {len(es)} clips, {mins:.1f} of {GOAL_MINUTES} minutes.{err}")

    def closeEvent(self, ev):
        if self.recorder is not None:
            self.recorder.cancel()
        super().closeEvent(ev)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_theme(app, Config.load().theme)
    w = Window()
    w.show()
    sys.exit(app.exec())
