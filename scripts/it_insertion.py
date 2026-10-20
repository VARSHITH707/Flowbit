"""Integration checks 3.2-3.8 against owned Tk windows. Prints PASS/FAIL per case."""
import sys; sys.path.insert(0, "scripts")
from it_helpers import *
import time
import win32clipboard as wc
from voicetype import insertion as ins

results = []
def check(name, cond, extra=""):
    results.append(cond); print(("PASS " if cond else "FAIL ") + name, extra)

A, B = Target("VT Target A"), Target("VT Target B")
try:
    assert A.focus(), "could not focus A"
    hwnd = ins.foreground(); check("3.2 foreground captured == A", hwnd == A.hwnd)

    r = ins.insert("Hello world.", hwnd); check("3.3 single-line type", r.status == "inserted" and A.text() == "Hello world.", repr(A.text()))

    A.focus(); u = "héllo wörld — 日本語 😀 ñ"
    r = ins.insert(u, hwnd); check("3.5 unicode+emoji", r.status == "inserted" and A.text().endswith(u), repr(A.text()[-30:]))

    ins.set_clipboard("ORIGINAL CLIP"); A.focus()
    ml = "line one\nline two\n\nnew paragraph"
    before = A.text(); r = ins.insert(ml, hwnd)
    check("3.5 multiline via paste", r.status == "inserted" and A.text() == before + ml, repr(A.text()[len(before):]))
    _, clip = ins.clipboard_snapshot(); check("3.7 clipboard restored after paste", clip == "ORIGINAL CLIP", repr(clip))

    A.focus(); long = ("The quick brown fox jumps over the lazy dog. " * 120).strip()
    before = A.text(); r = ins.insert(long, hwnd); check("3.5 long (%d chars) type" % len(long), r.status == "inserted" and A.text() == before + long)
    A.focus(); before = A.text(); r = ins.insert(long + "\nend", hwnd); check("3.5 long multiline paste", r.status == "inserted" and A.text() == before + long + "\nend")

    # non-text clipboard must not be clobbered
    fmt = wc.RegisterClipboardFormat("VoiceTypeTest"); wc.OpenClipboard(); wc.EmptyClipboard(); wc.SetClipboardData(fmt, b"binary-data"); wc.CloseClipboard()
    A.focus(); r = ins.insert("after\nbinary", hwnd)
    wc.OpenClipboard(); still = wc.IsClipboardFormatAvailable(fmt); wc.CloseClipboard()
    check("3.7 non-text clipboard not overwritten", still, f"status={r.status}")

    # 3.6 focus changed during recording: target A captured, user switches to B
    ins.set_clipboard("x"); a_before, b_before = A.text(), B.text()
    B.focus(); r = ins.insert("SHOULD NOT BE TYPED", A.hwnd)
    _, clip = ins.clipboard_snapshot()
    check("3.6 focus changed -> copied, nothing typed anywhere", r.status == "copied" and A.text() == a_before and B.text() == b_before and clip == "SHOULD NOT BE TYPED", r.detail)

    # target closed
    hb = B.hwnd; B.close(); time.sleep(0.6); r = ins.insert("gone", hb)
    check("3.6 target window gone -> copied", r.status == "copied", r.detail)
finally:
    A.close()
    try: B.close()
    except Exception: pass
print(f"\n{sum(results)}/{len(results)} passed"); sys.exit(0 if all(results) else 1)
