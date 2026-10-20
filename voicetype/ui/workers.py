"""Run blocking work off the UI thread and report back through Qt signals."""
import threading

from PySide6.QtCore import QObject, Signal


class Job(QObject):
    progress = Signal(int, int)
    finished = Signal(object)  # result or None
    failed = Signal(str)

    def __init__(self, fn, *args):
        super().__init__()
        self._fn, self._args = fn, args

    def start(self) -> "Job":
        threading.Thread(target=self._run, daemon=True, name="job").start()
        return self

    def _run(self) -> None:
        try:
            self.finished.emit(self._fn(*self._args, self.progress.emit) if self._wants_progress() else self._fn(*self._args))
        except Exception as e:
            self.failed.emit(str(e))

    def _wants_progress(self) -> bool:
        return getattr(self._fn, "wants_progress", False)


def with_progress(fn):
    fn.wants_progress = True
    return fn
