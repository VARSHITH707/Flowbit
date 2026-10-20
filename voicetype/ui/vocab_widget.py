import json
import os

from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

MAX_IMPORT_BYTES, MAX_ENTRY_CHARS = 1_000_000, 200


class VocabEditor(QWidget):
    """Custom vocabulary: 'Word' fixes spelling/case, 'spoken phrase=>Written' replaces it."""

    def __init__(self, entries):
        super().__init__()
        self.list = QListWidget()
        self.list.setAccessibleName("Custom vocabulary")
        self.list.addItems(entries)
        add, edit, rm = QPushButton("Add"), QPushButton("Edit"), QPushButton("Remove")
        imp, exp = QPushButton("Import..."), QPushButton("Export...")
        add.clicked.connect(self.add)
        edit.clicked.connect(self.edit)
        rm.clicked.connect(self.remove)
        imp.clicked.connect(self.import_)
        exp.clicked.connect(self.export)
        hint = QLabel("One entry per line. Use  word  to fix spelling, or  spoken phrase=>Written form.", objectName="muted")
        hint.setWordWrap(True)
        row = QHBoxLayout()
        for b in (add, edit, rm, imp, exp):
            row.addWidget(b)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(hint)
        lay.addWidget(self.list)
        lay.addLayout(row)

    def entries(self) -> list[str]:
        return [self.list.item(i).text() for i in range(self.list.count())]

    def add(self):
        t, ok = QInputDialog.getText(self, "Add vocabulary", "Word, or spoken=>Written:")
        if ok and t.strip():
            self.list.addItem(t.strip())

    def edit(self):
        it = self.list.currentItem()
        if it:
            t, ok = QInputDialog.getText(self, "Edit vocabulary", "Word, or spoken=>Written:", text=it.text())
            if ok and t.strip():
                it.setText(t.strip())

    def remove(self):
        for it in self.list.selectedItems():
            self.list.takeItem(self.list.row(it))

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export vocabulary", "vocabulary.json", "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.entries(), f, indent=2, ensure_ascii=False)

    def import_(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import vocabulary", "", "JSON or text (*.json *.txt)")
        if not path:
            return
        try:
            if os.path.getsize(path) > MAX_IMPORT_BYTES:
                raise ValueError("file is larger than 1 MB")
            raw = open(path, encoding="utf-8-sig").read()
            items = json.loads(raw) if path.lower().endswith(".json") else raw.splitlines()
            if not isinstance(items, list):
                raise ValueError("expected a list")
            have = set(self.entries())
            for s in (str(x).strip()[:MAX_ENTRY_CHARS] for x in items):
                if s and s not in have:
                    self.list.addItem(s)
                    have.add(s)
        except Exception as e:
            QMessageBox.warning(self, "Import failed", f"Could not read that file: {e}")
