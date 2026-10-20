from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QProgressBar,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import models
from .workers import Job, with_progress


class ModelsPage(QWidget):
    changed = Signal()  # active model or download state changed

    def __init__(self, cfg_holder, transcriber):
        super().__init__()
        self.cfg_holder, self.transcriber, self._job = cfg_holder, transcriber, None
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Model", "Size", "Status", ""])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.dl, self.use, self.rm = QPushButton("Download", objectName="primary"), QPushButton("Use this model"), QPushButton("Delete from disk", objectName="danger")
        self.dl.clicked.connect(self.download)
        self.use.clicked.connect(self.make_active)
        self.rm.clicked.connect(self.remove)
        self.bar = QProgressBar()
        self.bar.hide()
        self.msg = QLabel("", objectName="muted")
        self.msg.setWordWrap(True)
        note = QLabel("Models are downloaded once from Hugging Face, then everything runs offline on this PC. "
                      "large-v3-turbo is the most accurate; small is the fastest and lightest.", objectName="muted")
        note.setWordWrap(True)
        row = QHBoxLayout()
        for b in (self.dl, self.use, self.rm):
            row.addWidget(b)
        row.addStretch()
        lay = QVBoxLayout(self)
        lay.addWidget(note)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.bar)
        lay.addWidget(self.msg)
        lay.addLayout(row)
        self.table.itemSelectionChanged.connect(self._buttons)
        self.refresh()

    def refresh(self):
        sel = self._name()
        self.table.setRowCount(len(models.MODELS))
        active = self.cfg_holder.cfg.model
        for r, (name, size) in enumerate(models.MODELS.items()):
            ok = models.is_available(name)
            status = ("Downloaded" if ok else "Not downloaded") + (" - active" if name == active else "")
            for c, v in enumerate((name, size, status)):
                self.table.setItem(r, c, QTableWidgetItem(v))
            if name == (sel or active):
                self.table.selectRow(r)
        self._buttons()

    def _name(self):
        r = self.table.currentRow()
        it = self.table.item(r, 0) if r >= 0 else None
        return it.text() if it else None

    def _buttons(self):
        name, busy = self._name(), self._job is not None
        ok = bool(name) and models.is_available(name)
        self.dl.setEnabled(bool(name) and not ok and not busy)
        self.use.setEnabled(ok and name != self.cfg_holder.cfg.model and not busy)
        self.rm.setEnabled(ok and not busy and name != self.cfg_holder.cfg.model)

    def download(self):
        name = self._name()
        self.bar.setValue(0)
        self.bar.show()
        self.msg.setText(f"Downloading {name}...")
        job = self._job = Job(with_progress(lambda n, cb: models.download(n, cb)), name)
        job.progress.connect(lambda d, t: (self.bar.setMaximum(max(t, 1)), self.bar.setValue(d)))
        job.finished.connect(lambda _: self._done(f"{name} downloaded. You can use it offline now."))
        job.failed.connect(lambda e: self._done(f"Download failed: {e}. Check your internet connection and try again.", True))
        job.start()
        self._buttons()

    def _done(self, text, error=False):
        self._job = None
        self.bar.hide()
        self.msg.setText(text)
        self.msg.setObjectName("error" if error else "muted")
        self.msg.setStyleSheet("")  # re-polish for the new objectName
        self.refresh()
        self.changed.emit()

    def make_active(self):
        self.cfg_holder.cfg.model = self._name()
        self.cfg_holder.cfg.save()
        self.msg.setText(f"Active model: {self._name()} (loads on next use).")
        self.refresh()
        self.changed.emit()

    def remove(self):
        name = self._name()
        if QMessageBox.question(self, "Delete model", f"Remove {name} from disk? You can download it again later.") == QMessageBox.Yes:
            try:
                models.delete(name)
            except Exception as e:
                QMessageBox.warning(self, "Delete failed", str(e))
            self.refresh()
            self.changed.emit()
