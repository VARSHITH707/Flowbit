
from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from .. import models
from ..audio import list_inputs
from ..config import CHOICES, data_dir
from ..hotkeys import conflicts, parse
from .vocab_widget import VocabEditor

LANGS = [("", "Auto-detect"), ("en", "English"), ("es", "Spanish"), ("fr", "French"), ("de", "German"), ("it", "Italian"),
         ("pt", "Portuguese"), ("nl", "Dutch"), ("ru", "Russian"), ("uk", "Ukrainian"), ("pl", "Polish"), ("tr", "Turkish"),
         ("ar", "Arabic"), ("hi", "Hindi"), ("bn", "Bengali"), ("ta", "Tamil"), ("te", "Telugu"), ("ml", "Malayalam"),
         ("ja", "Japanese"), ("ko", "Korean"), ("zh", "Chinese"), ("id", "Indonesian"), ("vi", "Vietnamese"), ("th", "Thai")]
STYLE_LABELS = {"email": "Email apps", "work": "Work chat (Slack, Teams)", "personal": "Personal chat (WhatsApp, Discord)",
                "code": "Code editors and terminals", "other": "Everything else"}
HOTKEY_LABELS = {"hold": "Push to talk (hold)", "toggle": "Start / stop (toggle)", "cancel": "Cancel recording",
                 "undo": "Undo last insertion", "settings": "Open settings"}


def combo(items, current):
    c = QComboBox()
    for data, label in items:
        c.addItem(label, data)
    i = c.findData(current)
    c.setCurrentIndex(max(i, 0))
    return c


class SettingsPage(QWidget):
    saved = Signal()
    clear_history_requested = Signal()

    def __init__(self, cfg_holder):
        super().__init__()
        self.h = cfg_holder
        c = cfg_holder.cfg
        self.theme = combo([(k, k.capitalize()) for k in CHOICES["theme"]], c.theme)
        self.mascot = QCheckBox("Show the Flowbit mascot when idle (it always appears while recording)")
        self.mascot.setChecked(c.mascot_visible)
        self.opacity = QSpinBox(minimum=30, maximum=100, suffix=" %")
        self.opacity.setValue(round(c.mascot_opacity * 100))
        self.motion = QCheckBox("Reduce animation (no idle floating; recording still shows your voice level)")
        self.motion.setChecked(c.reduced_motion)
        self.reset_pos = QPushButton("Move mascot back to the bottom centre")
        self.reset_pos.clicked.connect(self._reset_mascot)
        self.mic = combo([(None, "System default")] + [(i, n) for i, n in list_inputs()], c.mic)
        self.model = combo([(m, f"{m}  ({s})") for m, s in models.MODELS.items()], c.model)
        self.device = combo([("auto", "Automatic (GPU if available)"), ("cuda", "GPU (NVIDIA)"), ("cpu", "CPU only")], c.device)
        self.lang = combo(LANGS, c.language)
        self.unload = QSpinBox(minimum=0, maximum=240, suffix=" min (0 = never)")
        self.unload.setValue(c.unload_minutes)
        self.keys = {k: QLineEdit(c.hotkeys[k]) for k in HOTKEY_LABELS}
        for k, w in self.keys.items():
            w.setAccessibleName(HOTKEY_LABELS[k] + " hotkey")
        self.mode = combo([("both", "Hold or toggle"), ("hold", "Hold to talk only"), ("toggle", "Toggle only")], c.recording_mode)
        self.maxsec = QSpinBox(minimum=5, maximum=3600, suffix=" s")
        self.maxsec.setValue(c.max_seconds)
        self.silence = QCheckBox("Stop automatically after a pause in speech")
        self.silence.setChecked(c.silence_stop)
        self.silence_s = QDoubleSpinBox(minimum=0.5, maximum=10, singleStep=0.5, suffix=" s of silence")
        self.silence_s.setValue(c.silence_seconds)
        self.silence_t = QDoubleSpinBox(minimum=0.1, maximum=20, singleStep=0.1, decimals=1, suffix=" % loudness counts as speech")
        self.silence_t.setValue(c.silence_threshold * 100)
        self.auto_insert = QCheckBox("Insert text automatically (otherwise only show and copy it)")
        self.auto_insert.setChecked(c.auto_insert)
        self.method = combo([("auto", "Automatic (paste, restores your clipboard)"), ("paste", "Always paste"), ("type", "Always type (slower)")], c.insertion_method)
        self.policy = combo([("copy", "Copy to clipboard, do not paste"), ("insert_anyway", "Insert into the window that is focused now")], c.focus_policy)
        self._ai_controls(c)
        self.vocab = VocabEditor(c.vocab)
        self.vocab_bias = QCheckBox("Also hint these words to the speech model (can add words; off is safer)")
        self.vocab_bias.setChecked(c.vocab_bias)
        self.hist_on = QCheckBox("Save transcripts to history")
        self.hist_on.setChecked(c.history_enabled)
        self.hist_days = QSpinBox(minimum=0, maximum=3650, suffix=" days (0 = keep until deleted)")
        self.hist_days.setValue(c.history_days)
        self.err = QLabel("", objectName="error")
        self.err.setWordWrap(True)

        self._build_layout()

    def _ai_controls(self, c):
        self.fmt = combo([("smart", "Smart Formatting: punctuation, lists, numbers, spoken commands"),
                          ("exact", "Exact Transcription: your words as recognised")], c.format_mode)
        self.ai_cleanup = QCheckBox("Smart: local AI removes fillers and self-corrections")
        self.ai_cleanup.setChecked(c.ai_cleanup)
        self.ai_punct = QCheckBox("Local AI adds missing punctuation (never changes your words)")
        self.ai_punct.setChecked(c.ai_punctuation)
        self.numbers = QCheckBox("Smart: numbers as digits (25, 3.5, 15%, $20)")
        self.numbers.setChecked(c.number_formatting)
        self.commands = QCheckBox("Smart: spoken commands (new line, first point, bullet point)")
        self.commands.setChecked(c.spoken_commands)
        self.commands_exact = QCheckBox("Exact: also obey new line / new paragraph")
        self.commands_exact.setChecked(c.commands_in_exact)
        self.preview = QCheckBox("Show the text and ask before inserting it")
        self.preview.setChecked(c.preview)
        self.llm = QLineEdit(c.llm_model)
        self.llm.setAccessibleName("Local AI model (Ollama)")
        self.styles = {cat: combo([("formal", "Formal"), ("casual", "Casual")], c.styles.get(cat, "formal")) for cat in STYLE_LABELS}
        self.learn = QCheckBox("Learn from my corrections (reads the box Flowbit typed into)")
        self.learn.setChecked(c.learn_from_edits)

    def _build_layout(self):
        def group(title, rows):
            g = QGroupBox(title)
            f = QFormLayout(g)
            for label, w in rows:
                f.addRow(label, w) if label else f.addRow(w)
            return g

        clear = QPushButton("Delete all history now", objectName="danger")
        clear.clicked.connect(self.clear_history_requested)
        folder = QPushButton("Open data folder")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir()))))
        priv = QLabel(f"Audio is processed on this PC and never stored. Settings and history live in {data_dir()}. "
                      "No telemetry is sent.", objectName="muted")
        priv.setWordWrap(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.addWidget(group("Appearance", [("Theme", self.theme), (None, self.mascot), ("Mascot opacity", self.opacity),
                                           (None, self.motion), (None, self.reset_pos)]))
        lay.addWidget(group("Microphone", [("Input device", self.mic)]))
        lay.addWidget(group("Speech recognition", [("Model", self.model), ("Run on", self.device), ("Language", self.lang), ("Free GPU memory after", self.unload)]))
        lay.addWidget(group("Shortcuts (e.g. ctrl+alt+d, ctrl+alt+t, ctrl+windows)", [(HOTKEY_LABELS[k], w) for k, w in self.keys.items()] + [("Mode", self.mode)]))
        lay.addWidget(group("Recording and insertion", [("Longest recording", self.maxsec), (None, self.silence), ("Pause length", self.silence_s), ("Speech level", self.silence_t), (None, self.auto_insert), (None, self.preview), ("Insert by", self.method), ("If focus changed", self.policy)]))
        lay.addWidget(group("Formatting", [("Mode", self.fmt), (None, self.numbers), (None, self.commands), (None, self.commands_exact),
                                           (None, self.ai_punct), (None, self.ai_cleanup), ("Local AI model (Ollama)", self.llm)]))
        lay.addWidget(group("Custom vocabulary and learning", [(None, self.vocab), (None, self.vocab_bias), (None, self.learn)]))
        lay.addWidget(group("Writing style per app (Smart mode)", [(STYLE_LABELS[k], w) for k, w in self.styles.items()]))
        lay.addWidget(group("Privacy and history", [(None, self.hist_on), ("Keep for", self.hist_days), (None, priv), (None, clear), (None, folder)]))
        save = QPushButton("Save settings", objectName="primary")
        save.clicked.connect(self.save)
        row = QHBoxLayout()
        row.addWidget(self.err, 1)
        row.addWidget(save)
        lay.addLayout(row)
        scroll = QScrollArea(widgetResizable=True)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _reset_mascot(self):
        self.h.cfg.mascot_pos = None
        self.reset_requested = True
        self.err.setText("The mascot goes back to the bottom centre when you save.")

    def focus_mic(self):
        self.mic.setFocus()

    def save(self):
        keys = {k: w.text().strip().lower() for k, w in self.keys.items()}
        try:
            for k, v in keys.items():
                parse(v)
        except ValueError as e:
            self.err.setText(f"{e}. Use modifiers (ctrl, alt, shift, windows) plus at most one key, e.g. ctrl+alt+space.")
            return
        if len(set(keys.values())) < len(keys):
            self.err.setText("Each hotkey must be different.")
            return
        for k in ("cancel", "undo", "settings"):
            if parse(keys[k])[1] is None:
                self.err.setText(f"'{HOTKEY_LABELS[k]}' needs a non-modifier key (for example ctrl+alt+z).")
                return
        clash = conflicts(keys)
        if clash:
            self.err.setText(clash)
            return
        c = self.h.cfg
        c.theme, c.mascot_visible, c.mic = self.theme.currentData(), self.mascot.isChecked(), self.mic.currentData()
        c.mascot_opacity, c.reduced_motion = self.opacity.value() / 100, self.motion.isChecked()
        c.model, c.device, c.language, c.unload_minutes = self.model.currentData(), self.device.currentData(), self.lang.currentData(), self.unload.value()
        c.hotkeys, c.recording_mode, c.max_seconds = keys, self.mode.currentData(), self.maxsec.value()
        c.silence_stop, c.silence_seconds, c.silence_threshold = self.silence.isChecked(), self.silence_s.value(), round(self.silence_t.value() / 100, 4)
        c.auto_insert, c.insertion_method, c.focus_policy = self.auto_insert.isChecked(), self.method.currentData(), self.policy.currentData()
        c.format_mode, c.ai_cleanup, c.ai_punctuation = self.fmt.currentData(), self.ai_cleanup.isChecked(), self.ai_punct.isChecked()
        c.number_formatting, c.spoken_commands, c.commands_in_exact = self.numbers.isChecked(), self.commands.isChecked(), self.commands_exact.isChecked()
        c.preview, c.vocab, c.vocab_bias = self.preview.isChecked(), self.vocab.entries(), self.vocab_bias.isChecked()
        c.llm_model, c.learn_from_edits = self.llm.text().strip() or c.llm_model, self.learn.isChecked()
        c.styles = {k: w.currentData() for k, w in self.styles.items()}
        c.history_enabled, c.history_days = self.hist_on.isChecked(), self.hist_days.value()
        try:
            c.save()
        except OSError as e:
            self.err.setText(f"Could not save settings: {e}")
            return
        self.err.setText("")
        self.saved.emit()
