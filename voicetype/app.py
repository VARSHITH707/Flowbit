"""Flowbit entry point. Run:  python -m voicetype   (add --quit-after 3000 for a smoke test)"""
import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QLockFile, QObject, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

import threading

from . import cleanup, insertion, memory, undo
from .config import Config, data_dir
from .dictation import ACTIVE, DONE, FAILED, IDLE, RECORDING, Dictation, Settings
from .history import History
from . import hotkeys as hk
from .hotkeys import Hotkeys
from .learner import EditWatcher
from .transcriber import Transcriber
from .ui.main_window import MainWindow
from .ui.mascot import Mascot, mascot_icon
from .ui.preview import COPY, INSERT, PreviewDialog
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
    toast = Signal(str)
    undo = Signal()
    preview = Signal(object)  # dict: text, target, event, answer


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
        self.mascot = Mascot()
        self.mascot.level_source = self.dictation.level  # its sound waves follow the live mic level
        self.mascot.menu_actions = [("Open Flowbit", lambda: self.window.show_tab("home")),
                                    ("Undo last insertion", self.undo_last), ("Settings", lambda: self.window.show_tab("settings")),
                                    ("Hide mascot when idle", self._hide_mascot)]
        self.last_insert: undo.Snapshot | None = None
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
        b.undo.connect(self.undo_last)
        b.toast.connect(lambda m: self.tray.showMessage("Flowbit", m, QSystemTrayIcon.Information, 3500))
        b.preview.connect(self._show_preview)
        self.mascot.clicked.connect(self.dictation.toggle)
        self.mascot.moved.connect(self._mascot_moved)
        w.home.undo_insert_requested.connect(self.undo_last)
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
        uses_ai = (c.format_mode == "smart" and c.ai_cleanup) or c.ai_punctuation
        if not uses_ai or self._warm_model == c.llm_model:
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
        self.tray.showMessage("Flowbit learned", shown, QSystemTrayIcon.Information, 3000)

    def _model_changed(self) -> None:
        if self.transcriber.loaded and self.transcriber.loaded_model != self.holder.cfg.model:
            self.transcriber.unload()  # free the old model's VRAM; the new one loads on next use

    def _dictation_settings(self) -> Settings:
        c = self.holder.cfg
        return Settings(device=c.mic, max_seconds=c.max_seconds, language=c.language or None, auto_insert=c.auto_insert,
                        silence_seconds=c.silence_seconds if c.silence_stop else 0, silence_threshold=c.silence_threshold)

    def _insert(self, text: str, target: int):
        """Runs on the transcription thread. Preview (optional), safe focus restore, insertion, undo snapshot."""
        c = self.holder.cfg
        if c.focus_policy == "insert_anyway":
            target = insertion.foreground()
        if c.preview:
            ask = {"text": text, "target": target, "event": threading.Event(), "answer": None}
            self.bridge.preview.emit(ask)
            ask["event"].wait()
            choice, text = ask["answer"]
            if choice == COPY:
                insertion.set_clipboard(text)
                return insertion.InsertResult("copied", "Copied to the clipboard (from the preview).")
            if choice != INSERT:
                return insertion.InsertResult("failed", "Cancelled in the preview; nothing was inserted.")
        if insertion.is_own_window(insertion.foreground()) and not insertion.is_own_window(target):
            insertion.focus_window(target)  # a Flowbit window (preview, settings) is in front: give the cursor back
        res = insertion.insert(text, target, c.insertion_method)
        if res.status == "inserted":
            self.last_insert = undo.capture(text, target)
        return res

    def _show_preview(self, ask: dict) -> None:
        exe, title = insertion.window_app(ask["target"])
        dlg = PreviewDialog(ask["text"], title or exe)
        dlg.exec()
        ask["answer"] = (dlg.choice, dlg.text())
        ask["event"].set()

    def undo_last(self) -> None:
        """Undo Last Insertion (shortcut, Home button, mascot menu). Runs off the UI thread; reports the outcome."""
        def run():
            ok, msg = undo.undo(self.last_insert)
            if ok:
                self.last_insert = None
            self.bridge.status.emit(msg)
            self.bridge.toast.emit(msg)
        threading.Thread(target=run, daemon=True, name="undo").start()

    def _mascot_moved(self, x: int, y: int) -> None:
        self.holder.cfg.mascot_pos = [x, y]
        self.holder.cfg.save()

    def _hide_mascot(self) -> None:
        self.holder.cfg.mascot_visible = False
        self.holder.cfg.save()
        self.apply_config()
        self.tray.showMessage("Flowbit", "The mascot now only appears while recording. Turn it back on in Settings.",
                              QSystemTrayIcon.Information, 4000)

    def apply_config(self) -> None:
        c = self.holder.cfg
        self.dictation.s = self._dictation_settings()
        apply_theme(self.qapp, c.theme)
        self.mascot.configure(c.mascot_visible, c.mascot_opacity, c.reduced_motion, c.mascot_pos)
        self.mascot.set_state(self.dictation.state if self.dictation.state in ACTIVE else IDLE)
        self._check_hotkeys()
        self.window.home.refresh_info()
        self._start_hotkeys()
        self._warm_llm()

    def _check_hotkeys(self) -> None:
        """Move off the old toggle default if another program owns it; report any other clash."""
        c = self.holder.cfg
        try:
            if c.hotkeys.get("toggle") == hk.OLD_TOGGLE and hk.registered_elsewhere(hk.OLD_TOGGLE):
                c.hotkeys["toggle"] = hk.DEFAULTS["toggle"]
                c.save()
                self.window.home.notice.setText(f"{hk.OLD_TOGGLE} is used by another program on this PC, so the toggle "
                                                f"shortcut is now {hk.DEFAULTS['toggle']} (change it in Settings).")
            clash = hk.conflicts(c.hotkeys)
            if clash:
                self.window.home.notice.setText("Shortcut problem: " + clash)
        except Exception as e:  # a failed check must never stop the app
            log.warning("hotkey check failed: %s", type(e).__name__)

    def _start_hotkeys(self) -> None:
        if self.hotkeys:
            self.hotkeys.stop_listening()
        mode = lambda *m: self.holder.cfg.recording_mode in m  # noqa: E731
        self.hotkeys = Hotkeys(
            on_start=lambda: mode("both", "hold") and self.dictation.start("hold"),
            on_stop=lambda: mode("both", "hold") and self.dictation.stop(),
            on_toggle=lambda: mode("both", "toggle") and self.dictation.toggle(),
            on_cancel=lambda: self.dictation.state in (RECORDING, PROCESSING) and self.dictation.cancel(),
            on_settings=lambda: self.bridge.show_tab.emit("settings"),
            on_undo=lambda: self.bridge.undo.emit(),
            bindings=self.holder.cfg.hotkeys)
        try:
            self.hotkeys.start()
        except RuntimeError as e:
            QMessageBox.warning(self.window, "Hotkeys unavailable", f"{e}\nYou can still use the Start button in the window.")

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(mascot_icon(64), self.window)
        menu = QMenu()
        for label, fn in (("Start / stop dictation", self.dictation.toggle), ("Undo last insertion", self.undo_last),
                          ("Open Flowbit", lambda: self.window.show_tab("home")),
                          ("Settings", lambda: self.window.show_tab("settings")), ("Quit", self.quit)):
            a = QAction(label, menu)
            a.triggered.connect(lambda _=False, f=fn: f())
            menu.addAction(a)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("Flowbit")
        self.tray.activated.connect(lambda r: self.window.show_tab("home") if r == QSystemTrayIcon.Trigger else None)
        self._menu = menu
        self.tray.show()

    # ---- UI-thread slots
    def _on_state(self, state: str, detail: str) -> None:
        self.mascot.set_state(state, detail, self.dictation.mode)
        self.window.home.on_state(state, detail, self.dictation.mode)
        if state == DONE and self.transcriber.notice:
            self.window.home.notice.setText(self.transcriber.notice)
        if state == FAILED:
            self.tray.showMessage("Flowbit", detail.splitlines()[0][:200] if detail else "Failed", QSystemTrayIcon.Warning, 4000)

    def _on_result(self, res, ins) -> None:
        c = self.holder.cfg
        self.window.home.set_transcript(res.text, res.raw)
        if res.note:
            self.window.home.notice.setText(res.note)
        if c.history_enabled:
            self.history.add(res.text, language=res.language, duration=res.duration, model=c.model, raw=res.raw)
            self.window.history.refresh()
        if ins is not None and ins.status == "copied":
            self.tray.showMessage("Flowbit", ins.detail, QSystemTrayIcon.Information, 4000)
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
        self.mascot.hide()
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
    qapp.setApplicationName("Flowbit")
    qapp.setWindowIcon(mascot_icon(256))
    qapp.setQuitOnLastWindowClosed(False)
    setup_logging()
    lock = QLockFile(str(data_dir() / "voicetype.lock"))
    lock.setStaleLockTime(15000)
    if not lock.tryLock(200):
        QMessageBox.information(None, "Flowbit", "Flowbit is already running (look for its icon in the tray).")
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
