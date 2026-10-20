import os, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import win32api, win32con, win32gui

class Target:
    """A Tk test window we own (safe to start/stop)."""
    def __init__(self, title):
        self.title = title
        self.out = Path(tempfile.gettempdir()) / f"vt_{title.replace(' ', '_')}_{os.getpid()}.txt"
        self.p = subprocess.Popen([str(ROOT / ".venv/Scripts/python.exe"), str(ROOT / "scripts/tk_target.py"), str(self.out), title])
        for _ in range(60):
            self.hwnd = win32gui.FindWindow(None, title)
            if self.hwnd: break
            time.sleep(0.1)
        else: raise RuntimeError("target not found")
        time.sleep(0.4)
    def focus(self):
        import win32process
        for _ in range(6):
            fg = win32gui.GetForegroundWindow(); me = win32api.GetCurrentThreadId()
            fg_t = win32process.GetWindowThreadProcessId(fg)[0] if fg else me
            win32process.AttachThreadInput(me, fg_t, True)  # no synthetic keys (Alt tap would arm menu mode)
            try: win32gui.SetForegroundWindow(self.hwnd)
            except Exception: pass
            finally: win32process.AttachThreadInput(me, fg_t, False)
            time.sleep(0.4)
            if win32gui.GetForegroundWindow() == self.hwnd: return True
            time.sleep(0.3)
        return False
    def text(self):
        return stable(self)
    def close(self):
        self.p.terminate(); self.p.wait(5)

def stable(t, quiet=0.8, maxw=90):
    """Wait until the target's text stops changing."""
    last, since, start = None, time.time(), time.time()
    while time.time() - start < maxw:
        cur = t.out.read_text(encoding="utf-8")
        if cur != last: last, since = cur, time.time()
        elif time.time() - since > quiet: break
        time.sleep(0.1)
    return last
