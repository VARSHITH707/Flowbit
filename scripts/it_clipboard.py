"""Real clipboard: after a dictation is pasted, whatever you had copied (browser HTML, image, files) is back exactly."""
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import win32clipboard as wc
import win32con

from it_helpers import Target
from voicetype import insertion as ins

res = []


def check(name, cond, extra=""):
    res.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name, extra)


def put(items):
    wc.OpenClipboard()
    try:
        wc.EmptyClipboard()
        for f, d in items:
            wc.SetClipboardData(f, d)
    finally:
        wc.CloseClipboard()


HTML = wc.RegisterClipboardFormat("HTML Format")
RTF = wc.RegisterClipboardFormat("Rich Text Format")
PNG = wc.RegisterClipboardFormat("PNG")
html = b"Version:0.9\r\nStartHTML:0000000105\r\nEndHTML:0000000170\r\n<html><body><b>copied from a browser</b></body></html>"
rtf = b"{\\rtf1\\ansi {\\b copied from a browser}}"
dib = struct.pack("<IiiHHIIiiII", 40, 2, 2, 1, 32, 0, 16, 0, 0, 0, 0) + bytes(range(16))  # 2x2 32-bit DIB
png = b"\x89PNG\r\n\x1a\n" + bytes(200)
files = (r"C:\Windows\win.ini", r"C:\Windows\System32\drivers\etc\hosts")
CASES = {
    "browser copy (text + HTML + RTF)": [(win32con.CF_UNICODETEXT, "copied from a browser"), (HTML, html), (RTF, rtf)],
    "image copy (DIB + PNG)": [(win32con.CF_DIB, dib), (PNG, png)],
    "Explorer file copy (CF_HDROP)": [(win32con.CF_HDROP, ins._dropfiles(files))],
}

A = Target("VT Clipboard Target")
try:
    for name, items in CASES.items():
        put(items)
        before = ins.capture_clipboard()
        A.focus()
        prev = A.text()
        r = ins.insert(f"dictated text for {name}", A.hwnd)
        time.sleep(0.3)
        after = ins.capture_clipboard()
        check(f"{name}: dictation pasted", r.status == "inserted" and A.text() == prev + f"dictated text for {name}", r.status)
        check(f"{name}: clipboard restored byte-for-byte", before is not None and before == after,
              f"{len(before or [])} formats before, {len(after or [])} after")
    wc.OpenClipboard()
    try:
        check("file list readable after restore", wc.GetClipboardData(win32con.CF_HDROP) == files)
    finally:
        wc.CloseClipboard()

    big = wc.RegisterClipboardFormat("VoiceType Big Test")
    put([(win32con.CF_UNICODETEXT, "big one"), (big, b"x" * (ins.MAX_CLIPBOARD_BYTES + 1))])
    check("over 64 MB: cannot be saved -> not overwritten", ins.capture_clipboard() is None)
    A.focus()
    prev = A.text()
    r = ins.insert(" typed instead", A.hwnd)
    time.sleep(0.5)
    wc.OpenClipboard()
    try:
        still = wc.IsClipboardFormatAvailable(big) and wc.GetClipboardData(win32con.CF_UNICODETEXT) == "big one"
    finally:
        wc.CloseClipboard()
    check("over 64 MB: text typed instead, clipboard untouched", r.status == "inserted" and A.text().endswith(" typed instead") and still)
finally:
    A.close()
    put([])
print(f"{sum(res)}/{len(res)} passed")
sys.exit(0 if all(res) else 1)
