"""VoiceType entry point. Run:  python -m voicetype   (add --quit-after 3000 for a smoke test)"""
import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QLockFile, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

import threading

from . import cleanup, insertion, memory
from .config import Config, data_dir
from .dictation import DONE, FAILED, PROCESSING, RECORDING, Dictation, Settings
from .history import History
from .hotkeys import Hotkeys
from .learner import EditWatcher
from .transcriber import Transcriber
from .ui.main_window import MainWindow
from .ui.pill import StatePill
from .ui.setup_dialog import SetupDialog
from .ui.theme import apply_theme

log = logging.getLogger("voicetype")


class CfgHolder:
    def __init__(self, cfg: Config):
        self.cfg = cfg


class Bridge(QObject):
    """Thread-safe hand-off from worker/hook threads to the UI thread."""
    state = Signal(str, str)
    result = Signal(object, object)  # (Result, InsertResult | None)
    status = Signal(str)
    show_tab = Signal(str)
    learned = Signal(object)  # list of (heard, written)


def tray_icon(color="#4f8cff") -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(22, 8, 20, 32, 10, 10)
    p.drawRect(30, 42, 4, 8)
    p.drawRoundedRect(18, 50, 28, 5, 2, 2)
    p.end()
    return QIcon(pm)


def setup_logging() -> None:
    h = RotatingFileHandler(data_dir() / "voicetype.log", maxBytes=500_000, backupCount=2, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(h)
    logging.getLogger().setLevel(logging.INFO)  # transcript text is never logged


class App:
    def __init__(self, qapp: QApplication):
        self.qapp = qapp
        self.holder = CfgHolder(Config.load())
        self.bridge = Bridge()
        self.history = History()
        self.history.prune(self.holder.cfg.history_days)
        self.transcriber = Transcriber(lambda: self.holder.cfg, on_status=self.bridge.status.emit)
        self.dictation = Dictation(lambda: self.transcriber, self._dictation_settings(), on_state=self.bridge.state.emit,
                                   on_result=self.bridge.result.emit, insert=self._insert, categorize=self._categorize)
        self.learner = EditWatcher(on_learned=self.bridge.learned.emit)
        self._warm_model = None
        self.window = MainWindow(self.holder, self.history, self.transcriber)
        self.pill = StatePill()
        self.hotkeys: Hotkeys | None = None
        self._build_tray()
        self._connect()
        self.idle_timer = QTimer(interval=60_000, timeout=lambda: self.transcriber.unload_if_idle(self.holder.cfg.unload_minutes))
        self.idle_timer.start()
        self.apply_config()

    # ---- wiring
    def _connect(self) -> None:
        b, w = self.bridge, self.window
        b.state.connect(self._on_state)
        b.result.connect(self._on_result)
        b.status.connect(lambda m: w.home.notice.setText(m))
        b.show_tab.connect(w.show_tab)
        b.learned.connect(self._on_learned)
        w.home.toggle_requested.connect(self.dictation.toggle)
        w.home.cancel_requested.connect(self.dictation.cancel)
        w.settings.saved.connect(self.apply_config)
        w.settings.clear_history_requested.connect(self._clear_history)
        w.models.changed.connect(self._model_changed)

    @staticmethod
    def _categorize(hwnd: int) -> str:
        exe, title = insertion.window_app(hwnd)
        return memory.app_category(exe, title)

    def _warm_llm(self) -> None:
        """Load the speech model and the local AI in the background so the first dictation is not slow."""
        c = self.holder.cfg
        threading.Thread(target=self._warm_speech, daemon=True, name="asr-warmup").start()
        if c.cleanup_mode != "smart" or self._warm_model == c.llm_model:
            return
        self._warm_model = c.llm_model

        def run():
            if not cleanup.warm_up(c.llm_model):
                self.bridge.status.emit("Smart mode: the local AI (Ollama) is not available, so text is inserted without AI cleanup. "
                                        "Install Ollama and run: ollama pull " + c.llm_model)
                self._warm_model = None
        threading.Thread(target=run, daemon=True, name="llm-warmup").start()

    def _warm_speech(self) -> None:
        try:
            if c := self.holder.cfg:
                if c.first_run_done:
                    self.transcriber.engine()  # loads once; reused by the first dictation
        except Exception as e:  # e.g. model not downloaded yet: the first dictation shows the real error
            log.info("speech warm-up skipped: %s", type(e).__name__)

    def _on_learned(self, pairs) -> None:
        self.window.memory.refresh()
        shown = ", ".join(f"{h} -> {w}" for h, w in pairs[:3])
        self.tray.showMessage("VoiceType learned", shown, QSystemTrayIcon.Information, 3000)

    def _model_changed(self) -> None:
        if self.transcriber.loaded and self.transcriber.loaded_model != self.holder.cfg.model:
            self.transcriber.unload()  # free the old model's VRAM; the new one loads on next use

    def _dictation_settings(self) -> Settings:
        c = self.holder.cfg
        return Settings(device=c.mic, max_seconds=c.max_seconds, language=c.language or None, auto_insert=c.auto_insert,
                        silence_seconds=c.silence_seconds if c.silence_stop else 0, silence_threshold=c.silence_threshold)

    def _insert(self, text: str, target: int):
        c = self.holder.cfg
        if c.focus_policy == "insert_anyway":
            target = insertion.foreground()
        return insertion.insert(text, target, c.insertion_method)

    def apply_config(self) -> None:
        c = self.holder.cfg
        self.dictation.s = self._dictation_settings()
        apply_theme(self.qapp, c.theme)
        self.pill.show_when_idle = c.show_idle_pill
        self.pill.set_state(self.dictation.state if self.dictation.state in (RECORDING, PROCESSING) else "idle")
        self.window.home.refresh_info()
        self._start_hotkeys()
        self._warm_llm()

    def _start_hotkeys(self) -> None:
        if self.hotkeys:
            self.hotkeys.stop_listening()
        mode = lambda *m: self.holder.cfg.recording_mode in m  # noqa: E731
        self.hotkeys = Hotkeys(
            on_start=lambda: mode("both", "hold") and self.dictation.start(),
            on_stop=lambda: mode("both", "hold") and self.dictation.stop(),
            on_toggle=lambda: mode("both", "toggle") and self.dictation.toggle(),
            on_cancel=lambda: self.dictation.state in (RECORDING, PROCESSING) and self.dictation.cancel(),
            on_settings=lambda: self.bridge.show_tab.emit("settings"),
            bindings=self.holder.cfg.hotkeys)
        try:
            self.hotkeys.start()
        except RuntimeError as e:
            QMessageBox.warning(self.window, "Hotkeys unavailable", f"{e}\nYou can still use the Start button in the window.")

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(tray_icon(), self.window)
        menu = QMenu()
        for label, fn in (("Start / stop dictation", self.dictation.toggle), ("Open VoiceType", lambda: self.window.show_tab("home")),
                          ("Settings", lambda: self.window.show_tab("settings")), ("Quit", self.quit)):
            a = QAction(label, menu)
            a.triggered.connect(lambda _=False, f=fn: f())
            menu.addAction(a)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("VoiceType")
        self.tray.activated.connect(lambda r: self.window.show_tab("home") if r == QSystemTrayIcon.Trigger else None)
        self._menu = menu
        self.tray.show()

    # ---- UI-thread slots
    def _on_state(self, state: str, detail: str) -> None:
        self.pill.set_state(state, detail)
        self.window.home.on_state(state, detail)
        if state == DONE and self.transcriber.notice:
            self.window.home.notice.setText(self.transcriber.notice)
        if state == FAILED:
            self.tray.showMessage("VoiceType", detail.splitlines()[0][:200] if detail else "Failed", QSystemTrayIcon.Warning, 4000)

    def _on_result(self, res, ins) -> None:
        c = self.holder.cfg
        self.window.home.set_transcript(res.text, res.raw)
        if res.note:
            self.window.home.notice.setText(res.note)
        if c.history_enabled:
            self.history.add(res.text, language=res.language, duration=res.duration, model=c.model, raw=res.raw)
            self.window.history.refresh()
        if ins is not None and ins.status == "copied":
            self.tray.showMessage("VoiceType", ins.detail, QSystemTrayIcon.Information, 4000)
        elif ins is None and c.auto_insert and c.learn_from_edits:  # pasted: watch for your corrections
            self.learner.watch(res.text, cleaned=res.text if res.raw.strip() != res.text.strip() else None)

    def _clear_history(self) -> None:
        if QMessageBox.question(self.window, "Delete history", "Permanently delete all saved transcripts?") == QMessageBox.Yes:
            self.history.clear()
            self.window.history.refresh()

    # ---- lifecycle
    def first_run(self) -> None:
        if not self.holder.cfg.first_run_done:
            SetupDialog(self.holder, self.window).exec()
            self.apply_config()

    def quit(self) -> None:
        log.info("shutting down")
        self.window.quitting = True
        if self.hotkeys:
            self.hotkeys.stop_listening()
        self.dictation.cancel()
        self.learner.cancel()
        self.transcriber.unload()
        self.history.close()
        self.tray.hide()
        self.pill.hide()
        self.qapp.quit()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="voicetype")
    ap.add_argument("--quit-after", type=int, default=0, help="exit after N ms (smoke test)")
    ap.add_argument("--hidden", action="store_true", help="start in the tray without opening the window")
    ap.add_argument("--selftest", metavar="WAV", help="headless check: transcribe a 16 kHz mono WAV and write JSON (see --selftest-out)")
    ap.add_argument("--selftest-out", default="selftest.json", metavar="JSON")
    ap.add_argument("--model", default="small", help="model for --selftest")
    args = ap.parse_args(argv)
    if args.selftest:
        from .selftest import run
        return run(args.selftest, args.selftest_out, args.model)

    qapp = QApplication(sys.argv[:1])
    qapp.setApplicationName("VoiceType")
    qapp.setQuitOnLastWindowClosed(False)
    setup_logging()
    lock = QLockFile(str(data_dir() / "voicetype.lock"))
    lock.setStaleLockTime(15000)
    if not lock.tryLock(200):
        QMessageBox.information(None, "VoiceType", "VoiceType is already running (look for its icon in the tray).")
        return 1
    app = App(qapp)
    app.first_run()
    if not args.hidden:
        app.window.show()
    if args.quit_after:
        QTimer.singleShot(args.quit_after, app.quit)
    code = qapp.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
