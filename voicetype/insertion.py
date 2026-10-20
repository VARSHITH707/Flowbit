"""Insert text into the window that had focus when recording started.

Policy: never paste into a different window. If focus moved (or insertion fails), the text is
copied to the clipboard instead and the caller is told so.
"""
import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass

import pywintypes
import win32clipboard as wc
import win32con
import win32gui

user32 = ctypes.WinDLL("user32", use_last_error=True)
ULONG_PTR = ctypes.c_size_t
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x2, 0x4
VK_CONTROL, VK_V = 0x11, 0x56
TYPE_CHUNK, TYPE_PAUSE = 1, 0.02  # chars per SendInput batch, seconds between batches (measured in Win11 Notepad: 1/0.02 is reliable for ASCII+CJK, larger batches garble)


class _KI(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _MI(ctypes.Structure):  # only for correct union size
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _U(ctypes.Union):
    _fields_ = [("ki", _KI), ("mi", _MI)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT


@dataclass
class InsertResult:
    status: str  # "inserted" | "copied" | "failed"
    detail: str = ""


def foreground() -> int:
    return win32gui.GetForegroundWindow()


def window_app(hwnd: int) -> tuple[str, str]:
    """(exe path, window title) of a window; ("", "") if unknown."""
    if not hwnd:
        return "", ""
    title = win32gui.GetWindowText(hwnd)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    h = k32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return "", title
    try:
        buf, n = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
        ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
        return (buf.value if ok else ""), title
    finally:
        k32.CloseHandle(h)


def _send(events: list[tuple[int, int, int]]) -> None:
    arr = (_INPUT * len(events))()
    for i, (vk, scan, flags) in enumerate(events):
        arr[i].type = 1
        arr[i].ki = _KI(vk, scan, flags, 0, 0)
    if user32.SendInput(len(events), arr, ctypes.sizeof(_INPUT)) != len(events):
        raise OSError(f"SendInput blocked (error {ctypes.get_last_error()}); target may be elevated")


def type_text(text: str) -> None:
    """Unicode key events in small paced chunks: some apps (Win11 Notepad) drop events sent in a flood."""
    units = text.replace("\r\n", "\n").replace("\n", "\r").encode("utf-16-le")  # Enter is typed as CR
    codes = [int.from_bytes(units[i:i + 2], "little") for i in range(0, len(units), 2)]
    for i in range(0, len(codes), TYPE_CHUNK):
        ev = []
        for c in codes[i:i + TYPE_CHUNK]:
            ev += [(0, c, KEYEVENTF_UNICODE), (0, c, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
        _send(ev)
        time.sleep(TYPE_PAUSE)


def _open_clipboard() -> None:
    for _ in range(20):
        try:
            wc.OpenClipboard()
            return
        except pywintypes.error:
            time.sleep(0.05)
    raise OSError("Clipboard is locked by another program")


def set_clipboard(text: str) -> None:
    _open_clipboard()
    try:
        wc.EmptyClipboard()
        wc.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        wc.CloseClipboard()


# Clipboard formats that are GDI handles, not memory: bitmaps/palettes come back via CF_DIB, which Windows
# synthesises; metafiles and owner-drawn formats cannot be round-tripped, so we never overwrite them.
_SKIP_HANDLES = {win32con.CF_BITMAP, win32con.CF_PALETTE}
_UNRESTORABLE = {win32con.CF_METAFILEPICT, win32con.CF_ENHMETAFILE, 0x80, 0x82, 0x83, 0x8E}
_SYNTHESISED = {win32con.CF_TEXT, win32con.CF_OEMTEXT}  # rebuilt by Windows from CF_UNICODETEXT
MAX_CLIPBOARD_BYTES = 64 * 2**20


def _formats() -> list[int]:
    fmts, f = [], 0
    while True:
        f = wc.EnumClipboardFormats(f)
        if not f:
            return fmts
        fmts.append(f)


def _dropfiles(paths) -> bytes:
    """CF_HDROP payload: DROPFILES header (wide) + double-null-terminated file list."""
    import struct
    return struct.pack("<IiiII", 20, 0, 0, 0, 1) + ("\0".join(paths) + "\0\0").encode("utf-16-le")


def capture_clipboard() -> list | None:
    """Everything on the clipboard as [(format, data)], or None if it cannot be saved and put back exactly."""
    _open_clipboard()
    try:
        items, total = [], 0
        for f in _formats():
            if f in _SYNTHESISED or f in _SKIP_HANDLES:
                continue
            if f in _UNRESTORABLE:
                return None
            data = wc.GetClipboardData(f)
            if f == win32con.CF_HDROP:
                data = _dropfiles(data)
            total += len(data) * (2 if isinstance(data, str) else 1)
            if total > MAX_CLIPBOARD_BYTES:
                return None
            items.append((f, data))
        return items
    except Exception:
        return None
    finally:
        wc.CloseClipboard()


def restore_clipboard(items: list) -> None:
    _open_clipboard()
    try:
        wc.EmptyClipboard()
        for f, data in items:
            wc.SetClipboardData(f, data)
    finally:
        wc.CloseClipboard()


def clipboard_snapshot() -> tuple[bool, str | None]:
    """(restorable, plain text if any)."""
    items = capture_clipboard()
    text = next((d for f, d in (items or []) if f == win32con.CF_UNICODETEXT), None)
    if items is None:  # still report the text when the rest cannot be captured
        _open_clipboard()
        try:
            if wc.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                text = wc.GetClipboardData(win32con.CF_UNICODETEXT)
        finally:
            wc.CloseClipboard()
    return items is not None, text


def read_control(control) -> str | None:
    """Text of a UI Automation control, or None. Many controls raise when asked; that just means unreadable."""
    for get in ("GetValuePattern", "GetTextPattern"):
        try:
            p = getattr(control, get)()
            if p:
                return p.Value if get == "GetValuePattern" else p.DocumentRange.GetText(-1)
        except Exception:  # nosec B110 - unreadable control, try the next pattern
            pass
    return None


# Focused controls that can never take typed text: pasting there would silently lose the dictation.
NON_TEXT_CONTROLS = {"ButtonControl", "SplitButtonControl", "CheckBoxControl", "RadioButtonControl", "MenuItemControl",
                     "TabItemControl", "HyperlinkControl", "ImageControl", "ScrollBarControl", "SliderControl",
                     "TreeItemControl", "ListItemControl", "HeaderItemControl"}


def focused_kind() -> str | None:
    """UI Automation control type of the keyboard focus (e.g. 'EditControl', 'ButtonControl'), or None if unknown."""
    try:
        import uiautomation as auto
        with auto.UIAutomationInitializerInThread():
            c = auto.GetFocusedControl()
            return c.ControlTypeName if c is not None else None
    except Exception:
        return None


def _occurrences(text: str) -> int | None:
    """How many times `text` is in the focused text box, or None if this app does not expose its text."""
    try:
        import uiautomation as auto
        with auto.UIAutomationInitializerInThread():
            c = auto.GetFocusedControl()
            v = read_control(c) if c is not None else None
    except Exception:
        return None
    if v is None:
        return None
    norm = lambda t: t.replace("\r\n", "\n").replace("\r", "\n")  # noqa: E731
    return norm(v).count(norm(text))


def _wait_landed(text: str, before: int, seconds: float) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        now = _occurrences(text)
        if now is None or now > before:
            return True
        time.sleep(0.03)
    return False


CTRL_V = [(VK_CONTROL, 0, 0), (VK_V, 0, 0), (VK_V, 0, KEYEVENTF_KEYUP), (VK_CONTROL, 0, KEYEVENTF_KEYUP)]


def paste_text(text: str, saved: list | None = None) -> None:
    """Ctrl+V with the whole clipboard (text, HTML, images, files...) saved and restored afterwards."""
    saved = capture_clipboard() if saved is None else saved
    if saved is None:
        raise OSError("Clipboard content cannot be restored; refusing to overwrite it")
    before = _occurrences(text)  # None: this app does not expose its text, so the paste cannot be confirmed
    set_clipboard(text)
    try:
        try:
            _send(CTRL_V)
        except OSError:
            try:  # never leave Ctrl stuck down if the batch was only partly delivered
                _send([(VK_V, 0, KEYEVENTF_KEYUP), (VK_CONTROL, 0, KEYEVENTF_KEYUP)])
            except OSError:
                pass
            raise
        # Confirm, never retry: a re-sent Ctrl+V produced duplicates when the first one arrived late or mangled.
        if before is not None and not _wait_landed(text, before, 0.8):
            raise OSError("the paste could not be confirmed")
        time.sleep(0.35 if before is None else 0.1)  # unconfirmed: give the app time to read the clipboard
    finally:
        restore_clipboard(saved)


def insert(text: str, target_hwnd: int, method: str = "auto") -> InsertResult:
    """method: auto (paste when the clipboard can be restored, else type) | type | paste."""
    if not text:
        return InsertResult("failed", "Nothing to insert.")
    try:
        if not target_hwnd or not win32gui.IsWindow(target_hwnd) or foreground() != target_hwnd:
            set_clipboard(text)
            return InsertResult("copied", "Focus changed since recording started; text copied to the clipboard.")
        if focused_kind() in NON_TEXT_CONTROLS:
            set_clipboard(text)
            return InsertResult("copied", "No text box has the cursor (a button or menu is selected). "
                                          "The text is on the clipboard: click into a text box and press Ctrl+V.")
        saved = capture_clipboard()
        if method == "paste" or (method == "auto" and saved is not None):
            paste_text(text, saved)
        else:
            type_text(text)
        return InsertResult("inserted")
    except Exception as e:
        try:
            set_clipboard(text)
            return InsertResult("copied", f"Could not insert automatically ({e}); the text is on the clipboard: press Ctrl+V.")
        except Exception as e2:
            return InsertResult("failed", f"Insert and clipboard both failed: {e}; {e2}")
