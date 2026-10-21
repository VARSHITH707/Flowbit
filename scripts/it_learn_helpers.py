"""Shared helpers for real-app scripts (Notepad / Edge): focus a window and its text box, read the box."""
import time

import win32gui

SELECT_ALL = [(0x11, 0, 0), (0x41, 0, 0), (0x41, 0, 2), (0x11, 0, 2)]


def focus(hwnd):
    import win32api
    import win32process
    for _ in range(6):
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
        time.sleep(0.6)
        if win32gui.GetForegroundWindow() == hwnd:
            return True
    return False


def focus_editor(hwnd):
    """Win11 Notepad can open with a toolbar button focused: put the cursor in the document itself."""
    import uiautomation as auto
    with auto.UIAutomationInitializerInThread():
        root = auto.ControlFromHandle(hwnd)
        box = root.DocumentControl(searchDepth=12)
        if not box.Exists(1):
            box = root.EditControl(searchDepth=25)
        if box.Exists(3):
            box.SetFocus()
    time.sleep(0.3)


def notepads():
    out = []
    win32gui.EnumWindows(lambda h, _: out.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "Notepad" else None, None)
    return set(out)


def read_box() -> str:
    """Text of the focused box, line endings normalised ('' if unreadable)."""
    import uiautomation as auto

    from voicetype.insertion import read_control
    with auto.UIAutomationInitializerInThread():
        v = read_control(auto.GetFocusedControl()) or ""
    return v.replace("\r\n", "\n").replace("\r", "\n")


def close_own_tab(hwnd, filename: str) -> bool:
    """Close ONLY the test's own Notepad tab. Win11 Notepad restores the user's previous tabs into every new
    window, so closing the window (WM_CLOSE) would close the user's tabs too. Ctrl+W closes the active tab, and
    we only send it when the window title shows our file is the active tab."""
    from voicetype import insertion as ins
    focus(hwnd)
    if not win32gui.GetWindowText(hwnd).startswith(filename):
        print(f"   (left Notepad open: active tab is not {filename})")
        return False
    ins._send([(0x11, 0, 0), (0x57, 0, 0), (0x57, 0, 2), (0x11, 0, 2)])  # Ctrl+W
    time.sleep(0.8)
    return True
