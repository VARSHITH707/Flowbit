"""Check 3.1: hotkeys fire while another app has focus (keys are INJECTED with hardware scan codes, not physical).

Uses Shift+F9/F10/F11 on purpose: chords with Ctrl/Alt/Win can also trigger other dictation tools that may be
running on the same machine (this actually happened with a real Wispr Flow install), so the tests avoid them.
"""
import ctypes
import sys
import time

sys.path.insert(0, "scripts")
from it_helpers import *  # noqa: E402,F401,F403

from voicetype import insertion as ins  # noqa: E402
from voicetype.hotkeys import Hotkeys  # noqa: E402

SC = {"shift": (0x2A, 0), "f9": (0x43, 0), "f10": (0x44, 0), "f11": (0x57, 0), "esc": (0x01, 0),
      "a": (0x1E, 0)}
BINDINGS = {"hold": "shift+f9", "toggle": "shift+f10", "cancel": "esc", "settings": "shift+f11"}


def inj(k, up):
    sc, ext = SC[k]
    ctypes.windll.user32.keybd_event(0, sc, 0x8 | ext | (2 if up else 0), 0)


ev = []
hk = Hotkeys(lambda: ev.append("start"), lambda: ev.append("stop"), lambda: ev.append("toggle"),
             lambda: ev.append("cancel"), lambda: ev.append("settings"), bindings=BINDINGS)
A = Target("VT Hotkey Target")
res = []


def check(name, cond):
    res.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name, ev[-6:])


def run(down, up, wait=0.4):
    ev.clear()
    for k in down:
        inj(k, False); time.sleep(0.05)
    time.sleep(wait)
    for k in up:
        inj(k, True); time.sleep(0.05)
    time.sleep(0.3)
    return list(ev)


try:
    hk.start()
    assert A.focus()
    check("hold: start on press, stop on release", run(["shift", "f9"], ["f9", "shift"]) == ["start", "stop"])
    A.focus(); ev.clear()
    inj("shift", False); inj("f9", False)
    for _ in range(25):  # auto-repeat key-downs
        inj("f9", False); time.sleep(0.04)
    inj("f9", True); inj("shift", True); time.sleep(0.3)
    check("hold with 25 auto-repeat key-downs -> single start/stop", ev == ["start", "stop"])
    A.focus(); check("hold, other release order", run(["shift", "f9"], ["shift", "f9"]) == ["start", "stop"])
    A.focus(); check("toggle", run(["shift", "f10"], ["f10", "shift"]) == ["toggle"])
    A.focus(); check("cancel (esc)", run(["esc"], ["esc"]) == ["cancel"])
    A.focus(); check("open settings", run(["shift", "f11"], ["f11", "shift"]) == ["settings"])
    A.focus(); check("plain key without modifiers -> nothing fires", run(["a"], ["a"], wait=0.02) == [])
    leak = A.text()
    check("no chord key leaked; the plain 'a' passed through untouched", leak == "a")
    print("   text in the focused app:", repr(leak))
    print("foreground still target (no focus theft):", ins.foreground() == A.hwnd)
finally:
    hk.stop_listening()
    A.close()
print(f"{sum(res)}/{len(res)} passed")
sys.exit(0 if all(res) else 1)
