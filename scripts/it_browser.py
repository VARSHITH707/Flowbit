"""Check 3.4: insert into a browser <textarea> and <input>. Isolated browser profile + window; nothing of the user's is touched.
Read-back: the page mirrors the field value into document.title, which we read from the window."""
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import win32api
import win32con
import win32gui
import win32process

from voicetype import insertion as ins

BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
exe = next(b for b in BROWSERS if Path(b).exists())
work = Path(tempfile.mkdtemp(prefix="vt_browser_"))
page = work / "t.html"
page.write_text("""<!doctype html><meta charset=utf-8><title>VT Browser Test</title>
<textarea id=a autofocus rows=8 cols=60></textarea><br><input id=b size=60>
<script>
const a=document.getElementById('a'), b=document.getElementById('b');
function up(){ document.title='VT|'+(document.activeElement===b?'b':'a')+'|'+JSON.stringify(a.value)+'|'+JSON.stringify(b.value); }
a.addEventListener('input',up); b.addEventListener('input',up); up();
</script>""", encoding="utf-8")


def wins():
    out = {}
    win32gui.EnumWindows(lambda h, _: out.__setitem__(h, win32gui.GetWindowText(h)) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h).startswith("Chrome_WidgetWin") else None, None)
    return out


def focus(hwnd):
    for _ in range(6):  # Windows can refuse SetForegroundWindow right after another focus change
        me = win32api.GetCurrentThreadId()
        fg = win32gui.GetForegroundWindow()
        ft = win32process.GetWindowThreadProcessId(fg)[0] if fg else me
        win32process.AttachThreadInput(me, ft, True)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        finally:
            win32process.AttachThreadInput(me, ft, False)
        time.sleep(0.8)
        if win32gui.GetForegroundWindow() == hwnd:
            return True
    return False


def fields(hwnd):
    import json
    t = win32gui.GetWindowText(hwnd)
    _, which, rest = t.split("|", 2)
    dec = json.JSONDecoder()
    a, i = dec.raw_decode(rest)
    b, _ = dec.raw_decode(rest[i + 1:])  # skip the "|" separator; ignore the browser's title suffix
    return which, a, b


before = set(wins())
p = subprocess.Popen([exe, f"--user-data-dir={work / 'profile'}", "--no-first-run", "--no-default-browser-check",
                      "--new-window", "--window-size=900,600", page.as_uri()])
hwnd = None
for _ in range(80):
    for h, t in wins().items():
        if h not in before and t.startswith("VT"):
            hwnd = h
    if hwnd:
        break
    time.sleep(0.25)
if not hwnd:
    p.terminate()
    sys.exit("browser window not found")
time.sleep(1.0)
res = []


def check(name, cond, extra=""):
    res.append(cond)
    print(("PASS " if cond else "FAIL ") + name, extra)


try:
    check("focus browser window", focus(hwnd))
    target = ins.foreground()
    ins.set_clipboard("USER CLIPBOARD")
    r = ins.insert("Hello from VoiceType.", target)
    time.sleep(0.6)
    check("textarea: default path", r.status == "inserted" and fields(hwnd)[1] == "Hello from VoiceType.", repr(fields(hwnd)[1]))
    uni = " héllo wörld — 日本語 😀"
    r = ins.insert(uni, target)
    time.sleep(0.6)
    check("textarea: unicode+emoji", fields(hwnd)[1].endswith(uni), repr(fields(hwnd)[1][-25:]))
    r = ins.insert("\nline two\n\nnew paragraph", target)
    time.sleep(0.6)
    check("textarea: multiline", fields(hwnd)[1].endswith("\nline two\n\nnew paragraph"), repr(fields(hwnd)[1][-30:]))
    r = ins.insert(" typed", target, "type")
    time.sleep(0.8)
    check("textarea: typing fallback (ASCII)", fields(hwnd)[1].endswith(" typed"), repr(fields(hwnd)[1][-12:]))
    check("clipboard preserved", ins.clipboard_snapshot()[1] == "USER CLIPBOARD")
    # <input>: Tab from the textarea moves focus to the input
    ins._send([(0x09, 0, 0), (0x09, 0, 2)])
    time.sleep(0.4)
    r = ins.insert("into the input field", target)
    time.sleep(0.6)
    check("input field: default path", fields(hwnd)[2] == "into the input field", repr(fields(hwnd)))
finally:
    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    time.sleep(1.5)
    print("our browser window closed:", hwnd not in wins())
    # the isolated browser process exits with its last window; do not kill anything
print(f"{sum(res)}/{len(res)} passed")
sys.exit(0 if all(res) else 1)
