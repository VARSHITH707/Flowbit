"""Global hotkeys via a Win32 low-level keyboard hook (no admin needed, keys are never swallowed).

hold  : modifier/key chord; start on press, stop when any of its keys is released (push-to-talk)
toggle/cancel/settings : fire when the final key goes down with exactly the listed modifiers held

Limitation: Windows (UIPI) does not show keys typed into elevated windows to a non-elevated hook.
"""
import ctypes
import logging
import queue
import threading
from ctypes import wintypes

DEFAULTS = {"hold": "ctrl+alt+d", "toggle": "ctrl+alt+space", "cancel": "esc", "settings": "ctrl+alt+shift+v"}
MODS = {"ctrl", "alt", "shift", "windows"}
_VK = {0xA0: "shift", 0xA1: "shift", 0x10: "shift", 0xA2: "ctrl", 0xA3: "ctrl", 0x11: "ctrl",
       0xA4: "alt", 0xA5: "alt", 0x12: "alt", 0x5B: "windows", 0x5C: "windows",
       0x20: "space", 0x1B: "esc", 0x0D: "enter", 0x09: "tab", 0x08: "backspace"}
_VK.update({c: chr(c).lower() for c in range(0x30, 0x3A)})
_VK.update({c: chr(c).lower() for c in range(0x41, 0x5B)})
_VK.update({0x70 + i: f"f{i + 1}" for i in range(12)})

WH_KEYBOARD_LL, HC_ACTION = 13, 0
_DOWN, _UP = (0x100, 0x104), (0x101, 0x105)
user32, kernel32 = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("kernel32")
_HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.SetWindowsHookExW.argtypes = (ctypes.c_int, _HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


class _KBD(ctypes.Structure):
    _fields_ = [("vk", wintypes.DWORD), ("scan", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("extra", ctypes.c_size_t)]


def parse(binding: str) -> tuple[frozenset, str | None]:
    """'ctrl+alt+space' -> (frozenset({'ctrl','alt'}), 'space'); modifier-only -> (mods, None)."""
    parts = [p.strip().lower() for p in binding.split("+") if p.strip()]
    mods = frozenset(p for p in parts if p in MODS)
    keys = [p for p in parts if p not in MODS]
    if not parts or len(keys) > 1 or any(p not in set(_VK.values()) for p in parts):
        raise ValueError(f"Invalid hotkey {binding!r}")
    return mods, (keys[0] if keys else None)


class Hotkeys:
    def __init__(self, on_start, on_stop, on_toggle, on_cancel, on_settings, bindings=None):
        b = {**DEFAULTS, **(bindings or {})}
        h_mods, h_key = parse(b["hold"])
        self._hold = h_mods | ({h_key} if h_key else set())
        self._hold_mods, self._hold_key = h_mods, h_key
        self._swallowed: set[str] = set()
        self._combos = {name: parse(b[name]) for name in ("toggle", "cancel", "settings")}
        for name, (m, k) in self._combos.items():
            if k is None:
                raise ValueError(f"{name} hotkey needs a non-modifier key")
        self._cb = {"start": on_start, "stop": on_stop, "toggle": on_toggle, "cancel": on_cancel, "settings": on_settings}
        self._down: set[str] = set()
        self._holding = False
        self._hook_error_logged = False
        self._q: queue.Queue = queue.Queue()
        self._thread = None
        self._tid = None
        self._ready = threading.Event()
        self._proc = _HOOKPROC(self._on_key)  # keep a reference or it is garbage collected

    # --- lifecycle
    def start(self) -> None:
        if self._thread:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="hotkey-hook")
        self._thread.start()
        if not self._ready.wait(5) or self._tid is None:
            raise RuntimeError("Could not install the global keyboard hook")
        threading.Thread(target=self._dispatch, daemon=True, name="hotkey-dispatch").start()

    def stop_listening(self) -> None:
        if self._tid:
            user32.PostThreadMessageW(self._tid, 0x12, 0, 0)  # WM_QUIT
            self._thread.join(2)
        self._q.put(None)
        self._thread = self._tid = None
        self._ready.clear()
        self._down.clear()
        self._swallowed.clear()
        self._holding = False

    def _run(self) -> None:
        hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0)
        if not hook:
            self._ready.set()
            return
        self._tid = kernel32.GetCurrentThreadId()
        self._ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        user32.UnhookWindowsHookEx(hook)

    def _dispatch(self) -> None:  # callbacks run off the hook thread so a slow handler can't stall the keyboard
        while (name := self._q.get()) is not None:
            try:
                self._cb[name]()
            except Exception:
                logging.getLogger(__name__).exception("hotkey handler %s failed", name)

    # --- hook
    def _on_key(self, n_code, w_param, l_param):
        block = False
        try:
            if n_code == HC_ACTION:
                k = ctypes.cast(l_param, ctypes.POINTER(_KBD)).contents
                name = _VK.get(k.vk)
                if name and w_param in _DOWN:
                    block = self._key_down(name)
                elif name and w_param in _UP:
                    block = self._key_up(name)
        except Exception:  # an exception must never escape a hook callback; log the first one only (no key data)
            if not self._hook_error_logged:
                self._hook_error_logged = True
                logging.getLogger(__name__).exception("keyboard hook handler error")
        if block:
            return 1  # swallow: the chord's letter must not also be typed into the focused app
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _key_down(self, name: str) -> bool:
        """Returns True when this key press belongs to a hotkey chord and must not reach the focused app."""
        repeat = name in self._down
        self._down.add(name)
        mods_down = {x for x in self._down if x in MODS}
        swallow = False
        if self._hold_key and name == self._hold_key and self._hold_mods == mods_down:
            swallow = True
        for cmd, (mods, key) in self._combos.items():
            if name == key and mods == mods_down:
                swallow = swallow or bool(mods)  # never swallow a bare key such as Esc
                if not repeat:
                    self._q.put(cmd)
        if swallow:
            self._swallowed.add(name)
        if repeat:
            return name in self._swallowed
        if not self._holding and self._hold <= self._down:
            self._holding = True
            self._q.put("start")
        return swallow

    def _key_up(self, name: str) -> bool:
        self._down.discard(name)
        if self._holding and not self._hold <= self._down:
            self._holding = False
            self._q.put("stop")
        if name in self._swallowed:  # its key-down was swallowed, so swallow the matching key-up too
            self._swallowed.discard(name)
            return True
        return False
