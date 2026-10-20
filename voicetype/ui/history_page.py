import time

from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)


class HistoryPage(QWidget):
    def __init__(self, history):
        super().__init__()
        self.history, self._entries = history, []
        self.search = QLineEdit(placeholderText="Search transcripts...", clearButtonEnabled=True)
        self.search.setAccessibleName("Search transcripts")
        self.search.textChanged.connect(self.refresh)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["When", "Text", "Lang", "Seconds"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setWordWrap(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.empty = QLabel("No transcripts yet.", objectName="muted")
        self.copy_b = QPushButton("Copy")
        self.orig_b = QPushButton("Copy original")
        self.orig_b.setToolTip("What was recognised before AI cleanup")
        self.orig_b.clicked.connect(self.copy_original)
        self.export_b = QPushButton("Export...")
        self.del_b = QPushButton("Delete")
        self.clear_b = QPushButton("Clear all", objectName="danger")
        self.copy_b.clicked.connect(self.copy)
        self.export_b.clicked.connect(self.export)
        self.del_b.clicked.connect(self.delete)
        self.clear_b.clicked.connect(self.clear)
        row = QHBoxLayout()
        for b in (self.copy_b, self.orig_b, self.export_b, self.del_b):
            row.addWidget(b)
        row.addStretch()
        row.addWidget(self.clear_b)
        lay = QVBoxLayout(self)
        lay.addWidget(self.search)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.empty)
        lay.addLayout(row)
        self.refresh()

    def refresh(self, *_):
        self._entries = self.history.list(self.search.text())
        self.table.setRowCount(len(self._entries))
        for r, e in enumerate(self._entries):
            for c, v in enumerate((time.strftime("%Y-%m-%d %H:%M", time.localtime(e.ts)), e.text, e.language, f"{e.duration:.1f}")):
                self.table.setItem(r, c, QTableWidgetItem(v))
        self.table.resizeRowsToContents()
        self.empty.setVisible(not self._entries)
        self.empty.setText("No matches." if self.search.text() else "No transcripts yet.")
        for b in (self.copy_b, self.orig_b, self.export_b, self.del_b, self.clear_b):
            b.setEnabled(bool(self._entries))

    def _selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self._entries[r] for r in rows]

    def copy(self):
        sel = self._selected()
        if sel:
            QApplication.clipboard().setText("\n\n".join(e.text for e in sel))

    def copy_original(self):
        sel = self._selected()
        if sel:
            QApplication.clipboard().setText("\n\n".join(e.raw or e.text for e in sel))

    def export(self):
        path, flt = QFileDialog.getSaveFileName(self, "Export history", "voicetype-history", "JSON (*.json);;CSV (*.csv);;Text (*.txt)")
        if path:
            fmt = "csv" if "csv" in flt else "txt" if "txt" in flt else "json"
            if not path.lower().endswith("." + fmt):
                path += "." + fmt
            try:
                self.history.export(path, fmt)
            except Exception as e:
                QMessageBox.warning(self, "Export failed", str(e))

    def delete(self):
        for e in self._selected():
            self.history.delete(e.id)
        self.refresh()

    def clear(self):
        if QMessageBox.question(self, "Clear history", "Permanently delete all saved transcripts?") == QMessageBox.Yes:
            self.history.clear()
            self.refresh()
