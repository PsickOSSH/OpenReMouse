"""Thin ctypes helpers over the Win32 API: windows, controls, pixels, screen size."""
from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [_ENUMPROC, wintypes.LPARAM]
user32.EnumChildWindows.argtypes = [wintypes.HWND, _ENUMPROC, wintypes.LPARAM]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.EnableWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.SetFocus.argtypes = [wintypes.HWND]
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.GetPixel.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.GetPixel.restype = wintypes.DWORD
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

WM_CLOSE, BM_CLICK = 0x0010, 0x00F5
SW_HIDE, SW_SHOW, SW_RESTORE = 0, 5, 9


def _text(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def class_name(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def window_title(hwnd) -> str:
    return _text(hwnd)


def list_windows() -> list[tuple[int, str]]:
    """Visible top-level windows that have a title."""
    out: list[tuple[int, str]] = []

    @_ENUMPROC
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            t = _text(hwnd)
            if t:
                out.append((hwnd, t))
        return True

    user32.EnumWindows(cb, 0)
    return out


def _match(pattern: str, hwnd, title: str) -> bool:
    p = pattern.strip()
    if not p:
        return False
    if p.lower().startswith("class:"):
        return class_name(hwnd).lower() == p[6:].strip().lower()
    return p.lower() in title.lower()


def find_window(pattern: str):
    """First visible window whose title contains ``pattern`` (case-insensitive),
    or whose class equals ``class:Name``. An exact title match wins."""
    wins = list_windows()
    for hwnd, t in wins:
        if t.lower() == pattern.strip().lower():
            return hwnd
    for hwnd, t in wins:
        if _match(pattern, hwnd, t):
            return hwnd
    return None


def foreground_title() -> str:
    h = user32.GetForegroundWindow()
    return _text(h) if h else ""


def is_foreground(pattern: str) -> bool:
    h = user32.GetForegroundWindow()
    return bool(h) and _match(pattern, h, _text(h))


def activate(hwnd) -> bool:
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.keybd_event(0x12, 0, 0, 0)       # tapping ALT lets SetForegroundWindow succeed
    user32.keybd_event(0x12, 0, 2, 0)
    return bool(user32.SetForegroundWindow(hwnd))


def close(hwnd) -> None:
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


class _FLASHWINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]


def flash(hwnd, count: int = 3) -> None:
    info = _FLASHWINFO(ctypes.sizeof(_FLASHWINFO), hwnd, 3 | 12, count, 0)  # caption+tray, until count
    user32.FlashWindowEx(ctypes.byref(info))


def find_control(hwnd, pattern: str):
    """Child control of ``hwnd`` matching text (substring) or ``class:Name``."""
    found: list = []

    @_ENUMPROC
    def cb(child, _):
        if _match(pattern, child, _text(child)):
            found.append(child)
            return False
        return True

    user32.EnumChildWindows(hwnd, cb, 0)
    return found[0] if found else None


def control_click(h) -> None:
    user32.SendMessageW(h, BM_CLICK, 0, 0)


def control_enable(h, on: bool) -> None:
    user32.EnableWindow(h, bool(on))


def control_show(h, on: bool) -> None:
    user32.ShowWindow(h, SW_SHOW if on else SW_HIDE)


def control_focus(h) -> None:
    me = kernel32.GetCurrentThreadId()
    them = user32.GetWindowThreadProcessId(h, None)
    user32.AttachThreadInput(me, them, True)
    try:
        user32.SetFocus(h)
    finally:
        user32.AttachThreadInput(me, them, False)


def get_pixel(x: int, y: int):
    """(r, g, b) of the screen pixel, or None if it cannot be read."""
    dc = user32.GetDC(None)
    if not dc:
        return None
    try:
        c = gdi32.GetPixel(dc, int(x), int(y))
    finally:
        user32.ReleaseDC(None, dc)
    if c == 0xFFFFFFFF:
        return None
    return (c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF)


def virtual_screen() -> tuple[int, int, int, int]:
    """x, y, width, height of the whole desktop (all monitors)."""
    g = user32.GetSystemMetrics
    return g(76), g(77), g(78), g(79)


def monitors() -> list[tuple[int, int, int, int]]:
    """(x, y, width, height) of every monitor; falls back to the virtual screen."""
    rects: list[tuple[int, int, int, int]] = []
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
                               ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def cb(hmon, hdc, rect, lparam):
        r = rect.contents
        rects.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    try:
        user32.EnumDisplayMonitors(None, None, proto(cb), 0)
    except Exception:
        rects = []
    return rects or [virtual_screen()]
