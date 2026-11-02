"""Light / dark theme for the Tk UI (ttk 'clam' tuned for dark, native 'vista' for light)."""
from __future__ import annotations

import ctypes
import tkinter as tk
from tkinter import ttk

from . import settings

DARK_COLORS = dict(bg="#1e1e1e", panel="#2a2a2c", field="#2d2d30", fg="#e6e6e6", dim="#8a8a8a",
                   sel="#0e639c", border="#454545", hover="#3a3a3d")
LIGHT_COLORS = dict(bg="#f0f0f0", panel="#e5e5e5", field="#ffffff", fg="#000000", dim="#6d6d6d",
                    sel="#0078d7", border="#adadad", hover="#e1e1e1")
_dark = False


def colors() -> dict:
    return DARK_COLORS if _dark else LIGHT_COLORS


def is_dark() -> bool:
    return _dark


def system_prefers_dark() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def load_pref() -> bool:
    """Saved choice, else follow the Windows app theme."""
    t = settings.load().get("theme")
    return t == "dark" if t in ("dark", "light") else system_prefers_dark()


def save_pref(dark: bool) -> None:
    settings.save(theme="dark" if dark else "light")


def titlebar(win) -> None:
    """Make the native title bar follow the theme (Windows 10 2004+/11)."""
    try:
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        v = ctypes.c_int(1 if _dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(v), 4)
    except Exception:
        pass


def decorate(win) -> None:
    """Theme a freshly created Toplevel."""
    win.configure(bg=colors()["bg"])
    titlebar(win)


def style_menu(menu: tk.Menu) -> None:
    c = colors()
    menu.configure(bg=c["field"], fg=c["fg"], activebackground=c["sel"], activeforeground="#ffffff",
                   borderwidth=0)
    for child in menu.winfo_children():
        if isinstance(child, tk.Menu):
            style_menu(child)


def apply(root: tk.Tk, dark: bool, menus=()) -> None:
    global _dark
    _dark = dark
    c = colors()
    st = ttk.Style(root)
    if dark:
        st.theme_use("clam")
        st.configure(".", background=c["bg"], foreground=c["fg"], fieldbackground=c["field"],
                     bordercolor=c["border"], lightcolor=c["bg"], darkcolor=c["bg"], troughcolor=c["panel"],
                     insertcolor=c["fg"], selectbackground=c["sel"], selectforeground="#ffffff")
        st.map(".", foreground=[("disabled", c["dim"])])
        st.configure("TButton", background=c["panel"], padding=(8, 4), bordercolor=c["border"])
        st.map("TButton", background=[("pressed", c["sel"]), ("active", c["hover"])])
        st.configure("TNotebook", background=c["bg"], bordercolor=c["border"])
        st.configure("TNotebook.Tab", background=c["panel"], foreground=c["fg"], padding=(12, 5))
        st.map("TNotebook.Tab", background=[("selected", c["bg"]), ("active", c["hover"])])
        st.configure("Treeview", background=c["field"], fieldbackground=c["field"], foreground=c["fg"],
                     bordercolor=c["border"], rowheight=22)
        st.map("Treeview", background=[("selected", c["sel"])], foreground=[("selected", "#ffffff")])
        st.configure("Treeview.Heading", background=c["panel"], foreground=c["fg"], relief="flat")
        st.map("Treeview.Heading", background=[("active", c["hover"])])
        for w in ("TEntry", "TSpinbox", "TCombobox"):
            st.configure(w, fieldbackground=c["field"], foreground=c["fg"], arrowcolor=c["fg"],
                         insertcolor=c["fg"])
        st.map("TCombobox", fieldbackground=[("readonly", c["field"])], foreground=[("readonly", c["fg"])],
               selectbackground=[("readonly", c["field"])], selectforeground=[("readonly", c["fg"])])
        st.configure("TCheckbutton", background=c["bg"])
        st.map("TCheckbutton", background=[("active", c["bg"])],
               indicatorcolor=[("selected", c["sel"]), ("!selected", c["field"])])
        st.configure("TScrollbar", background=c["panel"], arrowcolor=c["fg"], bordercolor=c["bg"])
        st.map("TScrollbar", background=[("active", c["hover"])])
    else:
        st.theme_use("vista" if "vista" in st.theme_names() else "default")
    for pattern, opts in (("*TCombobox*Listbox", dict(background=c["field"], foreground=c["fg"],
                                                       selectBackground=c["sel"], selectForeground="#ffffff")),
                          ("*Menu", dict(background=c["field"], foreground=c["fg"],
                                         activeBackground=c["sel"], activeForeground="#ffffff"))):
        for k, v in opts.items():
            root.option_add("%s.%s" % (pattern, k), v)
    root.configure(bg=c["bg"])
    for m in menus:
        style_menu(m)
    titlebar(root)
