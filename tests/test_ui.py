import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractButton, QComboBox, QLineEdit, QMessageBox, QSpinBox, QWidget

from voicetype import models
from voicetype.config import Config
from voicetype.dictation import DONE, FAILED, IDLE, PROCESSING, RECORDING
from voicetype.history import History
from voicetype.transcriber import Transcriber
from voicetype.ui.history_page import HistoryPage
from voicetype.ui.home_page import HomePage, classify
from voicetype.ui.main_window import MainWindow
from voicetype.ui.models_page import ModelsPage
from voicetype.ui.setup_dialog import SetupDialog
from voicetype.ui.settings_page import SettingsPage


class Holder:
    def __init__(self):
        self.cfg = Config()


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("VOICETYPE_HOME", str(tmp_path))
    monkeypatch.setattr("voicetype.ui.settings_page.list_inputs", lambda: [(1, "Mic A"), (2, "Mic B")])
    monkeypatch.setattr("voicetype.ui.setup_dialog.list_inputs", lambda: [(1, "Mic A"), (2, "Mic B")])
    return tmp_path


def test_error_classification_gives_actionable_buttons():
    assert classify("Model 'x' is not downloaded yet.")[2] == "models"
    assert classify("Microphone unavailable: boom")[2] == "settings"
    assert classify("CUDA failed with error out of memory")[2] == "settings"
    assert classify("No speech detected.")[2] == "retry"
    assert classify("weird")[2] == "retry"


def test_home_states_and_error_panel():
    h = Holder()
    p = HomePage(h)
    got = []
    p.open_tab.connect(got.append)
    p.on_state(RECORDING)
    assert p.go.text() == "Stop" and p.cancel.isEnabled()
    p.on_state(PROCESSING)
    assert not p.go.isEnabled()
    p.on_state(FAILED, "Model 'm' is not downloaded yet.")
    assert not p.err_card.isHidden() and p.err_btn.text() == "Open Models"
    p.err_btn.click()
    assert got == ["models"]
    p.on_state(DONE)
    p.on_state(IDLE)
    assert p.go.isEnabled() and not p.cancel.isEnabled()


def test_settings_save_persists_and_reloads():
    h = Holder()
    s = SettingsPage(h)
    s.theme.setCurrentIndex(s.theme.findData("dark"))
    s.model.setCurrentIndex(s.model.findData("small"))
    s.lang.setCurrentIndex(s.lang.findData(""))
    s.mic.setCurrentIndex(s.mic.findData(2))
    s.maxsec.setValue(120)
    s.keys["toggle"].setText("ctrl+alt+f9")
    s.vocab.list.addItem("PySide6")
    saved = []
    s.saved.connect(lambda: saved.append(1))
    s.save()
    assert saved and s.err.text() == ""
    c = Config.load()  # fresh read from disk = survives restart
    assert (c.theme, c.model, c.language, c.mic, c.max_seconds, c.hotkeys["toggle"], c.vocab) == ("dark", "small", "", 2, 120, "ctrl+alt+f9", ["PySide6"])


def test_settings_rejects_bad_and_duplicate_hotkeys():
    s = SettingsPage(Holder())
    s.keys["toggle"].setText("ctrl+banana")
    s.save()
    assert "Invalid hotkey" in s.err.text() and not Config.path().exists()
    s.keys["toggle"].setText("ctrl+alt+d")  # same as hold
    s.save()
    assert "different" in s.err.text()
    s.keys["toggle"].setText("ctrl+alt")  # part of the hold chord ctrl+alt+d
    s.save()
    assert "overlap" in s.err.text()
    s.keys["toggle"].setText("ctrl+alt+t")
    s.keys["cancel"].setText("ctrl+alt")  # cancel needs a real key
    s.save()
    assert "non-modifier" in s.err.text()


def test_history_page_search_delete_clear(monkeypatch):
    hist = History()
    for t in ("alpha one", "beta two", "alpha three"):
        hist.add(t, "en", 1.0, "m")
    p = HistoryPage(hist)
    assert p.table.rowCount() == 3
    p.search.setText("alpha")
    assert p.table.rowCount() == 2
    p.table.selectRow(0)
    p.delete()
    assert p.table.rowCount() == 1
    p.search.setText("")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    p.clear()
    assert p.table.rowCount() == 0 and not p.empty.isHidden() and hist.list() == []


def test_models_page_status_and_activate(monkeypatch):
    monkeypatch.setattr(models, "is_available", lambda m: m != "medium")
    h = Holder()
    p = ModelsPage(h, Transcriber(lambda: h.cfg))
    status = {p.table.item(r, 0).text(): p.table.item(r, 2).text() for r in range(p.table.rowCount())}
    assert status["medium"] == "Not downloaded" and status["large-v3-turbo"].endswith("active")
    p.table.selectRow(list(models.MODELS).index("small"))
    p.make_active()
    assert Config.load().model == "small"
    p.table.selectRow(list(models.MODELS).index("medium"))
    assert p.dl.isEnabled() and not p.use.isEnabled()


def test_setup_dialog_finish_marks_first_run_done():
    h = Holder()
    d = SetupDialog(h)
    d.mic.setCurrentIndex(d.mic.findData(2))
    assert d.pages.count() == 4 and not d.back.isEnabled()
    for _ in range(3):
        d.next.click()
    assert d.next.text() == "Finish"
    d.next.click()
    c = Config.load()
    assert c.first_run_done and c.mic == 2


def test_everything_keyboard_reachable_and_labelled():
    h = Holder()
    w = MainWindow(h, History(), Transcriber(lambda: h.cfg))
    w.show()
    for page in (w.home, w.history, w.models, w.settings):
        for wid in page.findChildren(QWidget):
            if isinstance(wid, (QAbstractButton, QLineEdit, QComboBox, QSpinBox)) and wid.isVisibleTo(page) and not wid.objectName().startswith("qt_"):
                assert wid.focusPolicy() != Qt.NoFocus, f"{type(wid).__name__} not keyboard focusable"
                name = wid.accessibleName() or (wid.text() if isinstance(wid, QAbstractButton) else "")
                label_for = isinstance(wid, (QComboBox, QSpinBox)) or isinstance(wid, QLineEdit)
                assert name or label_for or wid.toolTip(), f"unlabelled {type(wid).__name__}"
    # every tab reachable by keyboard
    assert w.tabs.tabBar().focusPolicy() != Qt.NoFocus


def test_vocab_import_rejects_huge_and_bad_files(tmp_path, monkeypatch):
    from voicetype.ui import vocab_widget
    from voicetype.ui.vocab_widget import VocabEditor
    warned = []
    monkeypatch.setattr(vocab_widget.QMessageBox, "warning", lambda *a, **k: warned.append(a[2]))
    ed = VocabEditor(["keep"])
    big = tmp_path / "big.json"
    big.write_text("[" + ",".join(['"x"'] * 400_000) + "]")  # > 1 MB
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    good = tmp_path / "good.json"
    good.write_text('["alpha", "keep", "' + "z" * 500 + '"]')
    for f in (big, bad):
        monkeypatch.setattr(vocab_widget.QFileDialog, "getOpenFileName", lambda *a, f=f, **k: (str(f), ""))
        ed.import_()
    assert len(warned) == 2 and ed.entries() == ["keep"]
    monkeypatch.setattr(vocab_widget.QFileDialog, "getOpenFileName", lambda *a, **k: (str(good), ""))
    ed.import_()
    assert ed.entries()[:2] == ["keep", "alpha"] and len(ed.entries()) == 3 and len(ed.entries()[2]) == 200


def test_smart_settings_save_and_reload():
    s = SettingsPage(Holder())
    s.fmt.setCurrentIndex(s.fmt.findData("exact"))
    s.ai_cleanup.setChecked(False)
    s.llm.setText("llama3.2:3b")
    s.styles["email"].setCurrentIndex(s.styles["email"].findData("casual"))
    s.learn.setChecked(False)
    s.save()
    c = Config.load()
    assert (c.format_mode, c.ai_cleanup, c.llm_model, c.styles["email"], c.styles["work"], c.learn_from_edits) == (
        "exact", False, "llama3.2:3b", "casual", "formal", False)


def test_memory_page_lists_and_forgets():
    from voicetype import memory
    from voicetype.ui.memory_page import MemoryPage
    memory.learn([("cubernetes", "Kubernetes"), ("send", "sent")])
    p = MemoryPage()
    rows = {p.table.item(r, 0).text(): p.table.item(r, 3).text() for r in range(p.table.rowCount())}
    assert rows == {"cubernetes": "active", "send": "waiting for one more fix"}
    p.table.selectRow(0)
    p.forget_selected()
    assert p.table.rowCount() == 1


def test_home_undo_ai_edit_copies_original(qapp):
    from PySide6.QtWidgets import QApplication
    p = HomePage(Holder())
    p.set_transcript("Let's do coffee at 3.", "let's do coffee at 2 actually 3")
    assert p.undo.isEnabled()
    p.undo_ai_edit()
    assert QApplication.clipboard().text() == "let's do coffee at 2 actually 3" and not p.undo.isEnabled()
    p.set_transcript("Same text.", "Same text.")
    assert not p.undo.isEnabled()  # nothing to undo when the AI changed nothing
