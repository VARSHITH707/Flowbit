"""Memory tab: what Flowbit learned from your corrections (all stored locally in the memory folder)."""
import time

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import memory


class MemoryPage(QWidget):
    def __init__(self):
        super().__init__()
        intro = QLabel("When you fix a word Flowbit typed (for example cubernetes -> Kubernetes), it remembers the fix "
                       "and writes it your way next time. Names apply after one fix; other words after you fix them twice. "
                       "Everything stays in this PC's memory folder.", objectName="muted")
        intro.setWordWrap(True)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Heard", "Written as", "Times fixed", "Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setAccessibleName("Learned corrections")
        self.info = QLabel("", objectName="muted")
        self.forget_b = QPushButton("Forget selected")
        self.clear_b = QPushButton("Forget everything", objectName="danger")
        folder = QPushButton("Open memory folder")
        self.forget_b.clicked.connect(self.forget_selected)
        self.clear_b.clicked.connect(self.forget_all)
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(memory.memory_dir()))))
        row = QHBoxLayout()
        for b in (self.forget_b, folder):
            row.addWidget(b)
        row.addStretch()
        row.addWidget(self.clear_b)
        lay = QVBoxLayout(self)
        lay.addWidget(intro)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.info)
        lay.addLayout(row)
        self.refresh()

    def refresh(self):
        data = sorted(memory.learned(), key=lambda d: -d.get("last", 0))
        self._data = data
        self.table.setRowCount(len(data))
        for r, d in enumerate(data):
            status = "active" if memory.is_active(d) else "waiting for one more fix"
            for c, v in enumerate((d["heard"], d["written"], str(d.get("count", 1)), status)):
                self.table.setItem(r, c, QTableWidgetItem(v))
        n_ex = len(memory.examples())
        last = max((d.get("last", 0) for d in data), default=0)
        self.info.setText(f"{len(data)} learned words, {n_ex} style examples from your edits."
                          + (f" Last learned {time.strftime('%Y-%m-%d %H:%M', time.localtime(last))}." if last else ""))
        self.forget_b.setEnabled(bool(data))
        self.clear_b.setEnabled(bool(data) or n_ex > 0)

    def forget_selected(self):
        for r in sorted({i.row() for i in self.table.selectedIndexes()}):
            memory.forget(self._data[r]["heard"])
        self.refresh()

    def forget_all(self):
        if QMessageBox.question(self, "Forget everything", "Delete everything Flowbit learned from your corrections?") == QMessageBox.Yes:
            memory.clear_all()
            self.refresh()
