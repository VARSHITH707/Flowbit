"""Preview before insertion (optional, off by default): check or edit the text, then Insert, Copy or Cancel."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QVBoxLayout

INSERT, COPY, CANCEL = "insert", "copy", "cancel"


class PreviewDialog(QDialog):
    def __init__(self, text: str, target_name: str = "", parent=None):
        super().__init__(parent, Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Flowbit: check before inserting")
        self.resize(560, 300)
        self.choice = CANCEL
        self.edit = QPlainTextEdit(text)
        self.edit.setAccessibleName("Text to insert")
        where = QLabel(f"Insert into: {target_name}" if target_name else "Insert where your cursor was", objectName="muted")
        buttons = QDialogButtonBox()
        ins = buttons.addButton("Insert", QDialogButtonBox.AcceptRole)
        ins.setObjectName("primary")
        ins.setDefault(True)
        copy = buttons.addButton("Copy only", QDialogButtonBox.ActionRole)
        buttons.addButton(QDialogButtonBox.Cancel)
        ins.clicked.connect(lambda: self._done(INSERT))
        copy.clicked.connect(lambda: self._done(COPY))
        buttons.rejected.connect(lambda: self._done(CANCEL))
        lay = QVBoxLayout(self)
        lay.addWidget(where)
        lay.addWidget(self.edit, 1)
        lay.addWidget(buttons)

    def _done(self, choice: str) -> None:
        self.choice = choice
        self.accept() if choice != CANCEL else self.reject()

    def text(self) -> str:
        return self.edit.toPlainText()
