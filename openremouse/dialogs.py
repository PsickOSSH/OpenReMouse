"""Tk dialogs: generic form, on-screen picker, and the add / edit action dialogs."""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import actions as extra
from . import theme, winapi
from .i18n import tr
from .actions import Field
from .rms import Action


def pick_point(parent) -> tuple[int, int, str] | None:
    """Click catcher with one overlay per monitor. Returns (x, y, 'RRGGBB') of the clicked pixel, or None."""
    res: dict = {}
    tops: list[tk.Toplevel] = []

    def close_all(_e=None):
        for t in tops:
            try:
                t.destroy()
            except tk.TclError:
                pass

    def click(e):
        res["pt"] = (e.x_root, e.y_root)
        close_all()

    for (x, y, w, h) in winapi.monitors():
        top = tk.Toplevel(parent)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.attributes("-alpha", 0.25)
        top.configure(bg="black", cursor="crosshair")
        # "+-1920" (not "-1920"): in Tk a bare minus anchors to the right/bottom screen edge.
        top.geometry("%dx%d+%d+%d" % (w, h, x, y))
        tk.Label(top, text=tr("Clique sur le point à viser — Échap pour annuler"), bg="black", fg="white",
                 font=("Segoe UI", 16)).place(relx=0.5, rely=0.1, anchor="center")
        top.bind("<Button-1>", click)
        top.bind("<Escape>", close_all)
        top.bind("<Button-3>", close_all)
        tops.append(top)

    for t in tops:
        t.update_idletasks()
        t.lift()
    tops[0].focus_force()
    # Keep keyboard focus on an overlay (Escape needs it); re-grab it if it is lost.
    def keep_focus():
        if tops and tops[0].winfo_exists():
            try:
                if parent.focus_get() is None:
                    tops[0].focus_force()
            except (tk.TclError, KeyError):
                pass
            tops[0].after(200, keep_focus)
    tops[0].after(100, keep_focus)
    parent.wait_window(tops[0])
    close_all()
    if "pt" not in res:
        return None
    parent.update()
    time.sleep(0.15)                      # let the overlays disappear before reading the pixel
    px, py = res["pt"]
    c = winapi.get_pixel(px, py) or (0, 0, 0)
    return px, py, "%02X%02X%02X" % c


class FormDialog(tk.Toplevel):
    """Modal form built from a list of Fields. ``.result`` is a dict of strings, or None."""

    def __init__(self, parent, title, fields, values=None, pick=""):
        super().__init__(parent)
        self.title(tr(title))
        self.resizable(False, False)
        self.result = None
        self.fields = fields
        self.vars: dict[str, tk.StringVar] = {}
        values = values or {}
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        for r, f in enumerate(fields):
            ttk.Label(frm, text=tr(f.label)).grid(row=r, column=0, sticky="w", pady=3, padx=(0, 10))
            raw = str(values.get(f.key, f.default))
            v = tk.StringVar(value=raw)
            self.vars[f.key] = v
            if f.kind == "choice":
                w = ttk.Combobox(frm, textvariable=v, values=list(f.choices), state="readonly", width=30)
            elif f.kind == "bool":
                v.set("1" if raw in ("1", "True", "true") else "0")
                w = ttk.Checkbutton(frm, variable=v, onvalue="1", offvalue="0")
            else:
                w = ttk.Entry(frm, textvariable=v, width=46)
            w.grid(row=r, column=1, sticky="we")
            if f.kind == "file":
                ttk.Button(frm, text="…", width=3,
                           command=lambda v=v: v.set(filedialog.askopenfilename(parent=self) or v.get())
                           ).grid(row=r, column=2, padx=(4, 0))
        row = len(fields)
        if pick:
            ttk.Button(frm, text=tr("Viser à l'écran…"), command=self._pick).grid(row=row, column=1, sticky="w", pady=6)
            row += 1
        bar = ttk.Frame(frm)
        bar.grid(row=row, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(bar, text="OK", command=self._ok).pack(side="left", padx=4)
        ttk.Button(bar, text=tr("Annuler"), command=self.destroy).pack(side="left")
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        theme.decorate(self)
        self.transient(parent)
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        parent.wait_window(self)

    def _pick(self):
        # This dialog is modal (grab_set): a grab blocks all input to other windows of the app,
        # including the picker overlays. Release it while picking, then restore it.
        self.grab_release()
        self.withdraw()
        try:
            r = pick_point(self.master)
        finally:
            self.deiconify()
            try:
                self.grab_set()
            except tk.TclError:
                pass
        if r:
            for k, val in zip(("x", "y", "color"), r):
                if k in self.vars:
                    self.vars[k].set(str(val))

    def _ok(self):
        out = {}
        for f in self.fields:
            v = self.vars[f.key].get().strip() if f.kind != "str" else self.vars[f.key].get()
            try:
                if f.kind == "int":
                    v = str(int(float(v)))
                elif f.kind == "float":
                    v = str(float(v))
            except ValueError:
                messagebox.showerror(tr("Valeur invalide"), tr("« %s » doit être un nombre.", tr(f.label)), parent=self)
                return
            out[f.key] = v
        self.result = out
        self.destroy()


# ------------------------------------------------------------ action dialogs
_MOUSE_FIELDS = [Field("button", "Bouton", "choice", "LMouse", ("LMouse", "RMouse", "MMouse")),
                 Field("x", "X", "int", "0"), Field("y", "Y", "int", "0")]

# (menu label, key); key is "click" | "keypress" | "delay" | "cmd:<Name>"
MENU: list[tuple[str, list[tuple[str, str]]]] = [
    ("Souris", [("Clic", "click")]),
    ("Clavier", [("Touche", "keypress")] +
     [(extra.REGISTRY[n].label, "cmd:" + n) for n in ("Keystroke", "TypeText")]),
    ("Temps", [("Délai", "delay")]),
] + [(cat, [(s.label, "cmd:" + s.name) for s in extra.REGISTRY.values() if s.category == cat])
     for cat in extra.CATEGORIES if cat != "Clavier"]


def new_actions(parent, key: str) -> list[Action] | None:
    if key == "delay":
        d = FormDialog(parent, "Délai", [Field("s", "Durée (secondes)", "float", "1.0")]).result
        return [Action("delay", delay=float(d["s"]))] if d else None
    if key == "click":
        d = FormDialog(parent, "Clic", _MOUSE_FIELDS, pick="point").result
        if not d:
            return None
        return [Action("mouse", button=d["button"], pressed=p, x=int(d["x"]), y=int(d["y"]))
                for p in (True, False)]
    if key == "keypress":
        d = FormDialog(parent, "Touche", [Field("key", "Touche (ex. a, ENTER, F5)")]).result
        if not d or not d["key"]:
            return None
        return [Action("key", pressed=p, key=d["key"]) for p in (True, False)]
    spec = extra.REGISTRY[key.split(":", 1)[1]]
    d = FormDialog(parent, spec.label, spec.fields, pick=spec.pick).result
    return [Action("cmd", name=spec.name, args=d)] if d is not None else None


def edit_action(parent, a: Action) -> Action | None:
    """Edit one action. Returns the new Action or None if cancelled."""
    if a.kind == "delay":
        d = FormDialog(parent, "Délai", [Field("s", "Durée (secondes)", "float", str(a.delay))]).result
        return Action("delay", delay=float(d["s"])) if d else None
    if a.kind == "mouse":
        fs = [Field("button", "Bouton", "choice", a.button, ("LMouse", "RMouse", "MMouse")),
              Field("state", "État", "choice", "down" if a.pressed else "up", ("down", "up")),
              Field("x", "X", "int", str(a.x)), Field("y", "Y", "int", str(a.y))]
        d = FormDialog(parent, "Souris", fs, pick="point").result
        return Action("mouse", button=d["button"], pressed=d["state"] == "down",
                      x=int(d["x"]), y=int(d["y"])) if d else None
    if a.kind == "moves":
        fs = [Field("dx", "Décalage X (px)", "int", "0"), Field("dy", "Décalage Y (px)", "int", "0"),
              Field("scale", "Multiplicateur de durée (2 = deux fois plus lent)", "float", "1.0")]
        d = FormDialog(parent, tr("Mouvements (%d points)", len(a.moves)), fs).result
        if not d:
            return None
        dx, dy, sc = int(d["dx"]), int(d["dy"]), float(d["scale"])
        return Action("moves", moves=[(round(t * sc, 2), x + dx, y + dy) for t, x, y in a.moves])
    if a.kind == "key":
        fs = [Field("key", "Touche", "str", a.key),
              Field("state", "État", "choice", "down" if a.pressed else "up", ("down", "up"))]
        d = FormDialog(parent, "Touche", fs).result
        return Action("key", pressed=d["state"] == "down", key=d["key"]) if d else None
    if a.kind == "cmd" and a.name in extra.REGISTRY:
        spec = extra.REGISTRY[a.name]
        d = FormDialog(parent, spec.label, spec.fields, a.args, pick=spec.pick).result
        return Action("cmd", name=a.name, args=d) if d is not None else None
    d = FormDialog(parent, "Ligne brute", [Field("raw", "Texte", "str", a.raw or a.to_line())]).result
    if d is None:
        return None
    from .rms import parse_line
    return parse_line(d["raw"]) or a
