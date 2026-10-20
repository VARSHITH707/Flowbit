"""Learn from your corrections, like Wispr Flow's auto-learn: after pasting, watch the same text box; when you
leave it, compare what VoiceType typed with what you kept, and remember spelling fixes (memory.py rules).

Reads the focused control through Windows UI Automation, locally. Works where the app exposes its text
(verified: Win11 Notepad, Edge text fields); silently does nothing elsewhere. Never logs the text.
"""
import logging
import threading
import time

from . import memory

log = logging.getLogger(__name__)
WATCH_SECONDS, POLL_SECONDS = 90, 1.0


def _norm(t: str) -> str:
    return t.replace("\r\n", "\n").replace("\r", "\n")


def edited_segment(before: str, after: str, inserted: str) -> str | None:
    """What became of `inserted`, given the box text right after pasting (`before`) and later (`after`).
    Only answers when the text around the insertion is unchanged, so edits elsewhere are never misattributed."""
    before, after, inserted = _norm(before), _norm(after), _norm(inserted)
    i = before.rfind(inserted)
    if i < 0:
        return None
    prefix, suffix = before[:i], before[i + len(inserted):]
    if not (after.startswith(prefix) and after.endswith(suffix)) or len(after) < len(prefix) + len(suffix):
        return None
    return after[len(prefix):len(after) - len(suffix)]


from .insertion import read_control as _read  # noqa: E402


class EditWatcher:
    def __init__(self, on_learned=lambda pairs: None, seconds: float = WATCH_SECONDS, poll: float = POLL_SECONDS):
        self.on_learned, self.seconds, self.poll = on_learned, seconds, poll
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.trace: list[str] = []  # what happened, for diagnosis (never the text itself)

    def watch(self, inserted: str, cleaned: str | None = None) -> None:
        """Start watching the currently focused control (call right after a successful paste)."""
        self.cancel()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(inserted, cleaned, self._stop), daemon=True, name="edit-watch")
        self._thread.start()

    def cancel(self) -> None:
        self._stop.set()

    def _run(self, inserted: str, cleaned: str | None, stop: threading.Event) -> None:
        try:
            import uiautomation as auto
            with auto.UIAutomationInitializerInThread():
                self._watch(auto, inserted, cleaned, stop)
        except Exception:
            log.exception("edit watcher failed")  # no text in this log

    def _watch(self, auto, inserted: str, cleaned: str | None, stop: threading.Event) -> None:
        before, ctrl, give_up = None, None, time.time() + 2.0
        while time.time() < give_up and not stop.is_set():  # slow apps can take a moment to show the pasted text
            time.sleep(0.3)
            ctrl = auto.GetFocusedControl()
            before = _read(ctrl) if ctrl is not None else None
            if before is not None and _norm(inserted) in _norm(before):
                break
        if ctrl is None or before is None or _norm(inserted) not in _norm(before):
            self.trace.append(f"no readable text with our insertion ({ctrl.ControlTypeName if ctrl else None})")
            return  # this app does not expose its text, or the paste did not land here
        rid = ctrl.GetRuntimeId()
        self.trace.append(f"watching {ctrl.ControlTypeName} {ctrl.ClassName}")
        last, end = before, time.time() + self.seconds
        while time.time() < end and not stop.wait(self.poll):
            now = auto.GetFocusedControl()
            if now is None or now.GetRuntimeId() != rid:
                self.trace.append(f"focus moved to {now.ControlTypeName if now else None} {now.ClassName if now else ''}")
                break  # you left the text box: your edit is done
            text = _read(now)
            if text is not None:
                last = text
        seg = edited_segment(before, last, inserted)
        if seg is None or seg.strip() == inserted.strip():
            self.trace.append("no edit seen" if seg is not None else "text around the insertion changed")
            return
        self.trace.append(f"edit seen; {len(memory.corrections_from_edit(inserted, seg))} learnable word fixes")
        pairs = memory.corrections_from_edit(inserted, seg)
        new = memory.learn(pairs)
        if cleaned:
            memory.add_example(cleaned, seg.strip())
        if new:
            self.on_learned(new)
