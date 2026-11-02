"""Tkinter front-end: macro editor + recorder (tab 1), tasks / hotkeys / scheduler (tab 2)."""
from __future__ import annotations

import ctypes
import os
import queue
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import hotkeys, i18n, rms, tasks, theme
from .actions import Field
from .i18n import tr
from .dialogs import MENU, FormDialog, edit_action, new_actions
from .recorder import Recorder

TASK_FIELDS = [
    Field("name", "Nom"),
    Field("path", "Macro (.rms)", "file"),
    Field("hotkey", "Raccourci clavier (ex. ctrl+alt+1)"),
    Field("repeat", "Répétitions (0 = infini)", "int", "1"),
    Field("speed", "Vitesse", "float", "1.0"),
    Field("schedule", "Planification", "choice", "off", tasks.SCHEDULES),
    Field("at", "Heure (daily : HH:MM — once : AAAA-MM-JJ HH:MM)"),
    Field("every", "Intervalle en secondes (interval)", "int", "60"),
    Field("trigger", "Déclencheur", "choice", "off", tasks.TRIGGERS),
    Field("trigger_data", "Titre de fenêtre / nom du processus"),
    Field("enabled", "Activée", "bool", "1"),
]


def _dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # coordinates == real pixels
    except Exception:
        pass


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("OpenReMouse")
        root.geometry("760x520")
        self.actions: list[rms.Action] = []
        self.path: str | None = None
        self.recorder: Recorder | None = None
        self.hotkeys: hotkeys.Hotkeys | None = None
        self.q: queue.Queue = queue.Queue()
        self.status = tk.StringVar(value=tr("Prêt"))

        self.mgr = tasks.TaskManager(on_event=lambda m: self.q.put(lambda: self._event(m)))
        self.mgr.tasks = tasks.load_tasks()

        self.dark = tk.BooleanVar(value=theme.load_pref())
        self.lang = tk.StringVar(value=i18n.LANGS[i18n.get_lang()])
        self.repeat = tk.IntVar(value=1)
        self._build_ui()

        self.rebuild_hotkeys()
        self.mgr.start()
        root.after(50, self._pump)
        root.bind("<Control-s>", lambda e: self.save_file())
        root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        """(Re)build every widget; called again when the language changes."""
        for w in self.root.winfo_children():
            w.destroy()
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True)
        self.tab_macro, self.tab_tasks = ttk.Frame(nb), ttk.Frame(nb)
        nb.add(self.tab_macro, text=tr("Macro"))
        nb.add(self.tab_tasks, text=tr("Tâches planifiées"))
        foot = ttk.Frame(self.root)
        foot.pack(fill="x", side="bottom", before=nb)
        ttk.Checkbutton(foot, text=tr("Mode sombre"), variable=self.dark, command=self.apply_theme
                        ).pack(side="right", padx=8)
        box = ttk.Combobox(foot, textvariable=self.lang, values=list(i18n.LANGS.values()),
                           state="readonly", width=9)
        box.pack(side="right")
        box.bind("<<ComboboxSelected>>", lambda e: self.change_language())
        ttk.Label(foot, text=tr("Langue :")).pack(side="right", padx=(0, 4))
        ttk.Label(foot, textvariable=self.status, anchor="w").pack(side="left", fill="x", expand=True, padx=6, pady=3)
        self._build_macro()
        self._build_tasks()
        self.refresh()
        self.apply_theme(save=False)
        self.btn_rec.config(text=tr("Arrêter (F10)") if self.recorder else tr("Enregistrer (F10)"))
        self._set_play_button()

    def change_language(self):
        code = next((c for c, n in i18n.LANGS.items() if n == self.lang.get()), i18n.get_lang())
        if code == i18n.get_lang():
            return
        i18n.set_lang(code)
        self.status.set(tr("Prêt"))
        self._build_ui()

    # ------------------------------------------------------------ plumbing
    def _pump(self):                    # worker / hotkey threads post callables, Tk thread runs them
        try:
            while True:
                self.q.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(50, self._pump)

    def _event(self, msg: str):
        self.status.set(msg)
        self._set_play_button()
        self.refresh_tasks()

    def rebuild_hotkeys(self):
        m = {"f10": lambda: self.q.put(self.toggle_record),
             "f9": lambda: self.q.put(self.toggle_play)}
        reserved = {hotkeys.parse(s) for s in m}
        bad = []
        for t in self.mgr.tasks:
            if not (t.enabled and t.hotkey.strip()):
                continue
            try:
                combo = hotkeys.parse(t.hotkey)
            except ValueError:
                bad.append(t.hotkey)
                continue
            if combo in reserved:                   # F9 / F10 or an earlier task's combo
                bad.append(t.hotkey + tr(" (déjà utilisé)"))
                continue
            reserved.add(combo)
            m[t.hotkey] = lambda t=t: self.q.put(lambda: self._fire(t))
        if self.hotkeys:
            self.hotkeys.stop()
        self.hotkeys = hotkeys.Hotkeys(m)
        self.hotkeys.start()
        if bad:
            self.status.set(tr("Raccourci ignoré : ") + ", ".join(bad))

    def apply_theme(self, save: bool = True):
        theme.apply(self.root, self.dark.get(), menus=[self.menu])
        if save:
            theme.save_pref(self.dark.get())

    def _fire(self, t: tasks.Task):
        if self.recorder:
            return
        if self.mgr.current_task is t:      # pressing a running macro's hotkey again stops it
            self.mgr.stop()
            self.status.set(tr("Arrêt demandé : ") + t.name)
            return
        self.mgr.run_task(t)

    # --------------------------------------------------------- macro tab
    def _build_macro(self):
        f = self.tab_macro
        bar = ttk.Frame(f, padding=6)
        bar.pack(fill="x")
        self.btn_rec = ttk.Button(bar, text=tr("Enregistrer (F10)"), command=self.toggle_record)
        self.btn_play = ttk.Button(bar, text=tr("Lire (F9)"), command=self.toggle_play)
        self.btn_rec.pack(side="left", padx=2)
        self.btn_play.pack(side="left", padx=2)
        for text, cmd in ((tr("Nouveau"), self.new_file), (tr("Ouvrir…"), self.open_file),
                          (tr("Enregistrer"), self.save_file), (tr("Enregistrer sous…"), self.save_file_as)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)

        opt = ttk.Frame(f, padding=(6, 0))
        opt.pack(fill="x")
        ttk.Label(opt, text=tr("Répétitions (0 = infini):")).pack(side="left")
        ttk.Spinbox(opt, from_=0, to=100000, width=7, textvariable=self.repeat).pack(side="left", padx=4)
        ttk.Label(opt, text=tr("Vitesse:")).pack(side="left", padx=(12, 0))
        self.speed = tk.DoubleVar(value=1.0)
        ttk.Spinbox(opt, from_=0.1, to=20, increment=0.1, width=5, textvariable=self.speed).pack(side="left", padx=4)
        self.rec_moves = tk.BooleanVar(value=True)
        self.rec_keys = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt, text=tr("Enregistrer les mouvements"), variable=self.rec_moves).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(opt, text=tr("Clavier"), variable=self.rec_keys).pack(side="left", padx=4)

        body = ttk.Frame(f, padding=6)
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(body, columns=("n", "a"), show="headings", selectmode="extended")
        self.tree.heading("n", text="#")
        self.tree.heading("a", text=tr("Action"))
        self.tree.column("n", width=40, anchor="e", stretch=False)
        self.tree.column("a", width=500)
        sb = ttk.Scrollbar(body, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())
        self.tree.bind("<Delete>", lambda e: self.delete_selected())

        side = ttk.Frame(body, padding=(8, 0))
        side.pack(side="left", fill="y")
        self.btn_add = ttk.Button(side, text=tr("Ajouter ▾"), command=self._add_menu)
        self.btn_add.pack(fill="x", pady=2)
        for text, cmd in ((tr("Modifier"), self.edit_selected), (tr("Dupliquer"), self.duplicate_selected),
                          (tr("Supprimer"), self.delete_selected), (tr("Tout supprimer"), self.delete_all),
                          (tr("Monter"), lambda: self.move(-1)), (tr("Descendre"), lambda: self.move(1))):
            ttk.Button(side, text=text, command=cmd).pack(fill="x", pady=2)

        self.menu = tk.Menu(self.root, tearoff=0)
        for cat, items in MENU:
            sub = tk.Menu(self.menu, tearoff=0)
            for label, key in items:
                sub.add_command(label=tr(label), command=lambda k=key: self.add_action(k))
            self.menu.add_cascade(label=tr(cat), menu=sub)

    def _add_menu(self):
        b = self.btn_add
        self.menu.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def refresh(self, select: list[int] | None = None):
        self.tree.delete(*self.tree.get_children())
        for i, a in enumerate(self.actions):
            line = a.to_line()
            self.tree.insert("", "end", iid=str(i), values=(i + 1, line if len(line) < 140 else line[:137] + "..."))
        for i in select or []:
            if 0 <= i < len(self.actions):
                self.tree.selection_add(str(i))
                self.tree.see(str(i))

    def _selected(self) -> list[int]:
        return sorted(int(i) for i in self.tree.selection())

    def add_action(self, key: str):
        new = new_actions(self.root, key)
        if not new:
            return
        sel = self._selected()
        at = sel[-1] + 1 if sel else len(self.actions)
        self.actions[at:at] = new
        self.refresh(list(range(at, at + len(new))))

    def edit_selected(self):
        sel = self._selected()
        if not sel:
            return
        new = edit_action(self.root, self.actions[sel[0]])
        if new:
            self.actions[sel[0]] = new
            self.refresh([sel[0]])

    def duplicate_selected(self):
        sel = self._selected()
        if not sel:
            return
        import copy
        end = sel[-1] + 1
        self.actions[end:end] = [copy.deepcopy(self.actions[i]) for i in sel]
        self.refresh(list(range(end, end + len(sel))))

    def delete_selected(self):
        sel = self._selected()
        for i in reversed(sel):
            del self.actions[i]
        self.refresh([min(sel[0], len(self.actions) - 1)] if sel else None)

    def delete_all(self):
        if not self.actions:
            return
        if not messagebox.askyesno(tr("Tout supprimer"), tr("Supprimer les %d actions de la macro ?", len(self.actions))):
            return
        self.actions = []
        self.refresh()
        self.status.set(tr("Toutes les actions supprimées"))

    def move(self, d: int):
        sel = self._selected()
        if not sel or sel != list(range(sel[0], sel[-1] + 1)):
            return                                   # contiguous block only
        lo, hi = sel[0] + d, sel[-1] + d
        if lo < 0 or hi >= len(self.actions):
            return
        block = self.actions[sel[0]:sel[-1] + 1]
        del self.actions[sel[0]:sel[-1] + 1]
        self.actions[lo:lo] = block
        self.refresh(list(range(lo, hi + 1)))

    # recording / playing
    def toggle_record(self):
        if self.mgr.busy:
            return
        if self.recorder is None:
            self.recorder = Recorder(record_moves=self.rec_moves.get(), record_keys=self.rec_keys.get(),
                                     ignore_area=self._rec_button_rect)
            self.recorder.start()
            self.btn_rec.config(text=tr("Arrêter (F10)"))
            self.status.set(tr("Enregistrement…"))
        else:
            self.actions = self.recorder.stop()
            self.recorder = None
            self.btn_rec.config(text=tr("Enregistrer (F10)"))
            self.status.set(tr("%d actions enregistrées", len(self.actions)))
            self.refresh()

    def _rec_button_rect(self):
        b = self.btn_rec
        return b.winfo_rootx(), b.winfo_rooty(), b.winfo_rootx() + b.winfo_width(), b.winfo_rooty() + b.winfo_height()

    def toggle_play(self):
        if self.recorder:
            return
        if self.mgr.busy:
            self.mgr.stop()
            return
        if not self.actions:
            self.status.set(tr("Rien à lire : enregistre ou ouvre une macro"))
            return
        self.mgr.run(list(self.actions), self.repeat.get(), self.speed.get(),
                     label=self.path or tr("macro en cours"))
        self.status.set(tr("Lecture…"))
        self._set_play_button()

    def _set_play_button(self):
        self.btn_play.config(text=tr("Arrêter (F9)") if self.mgr.busy else tr("Lire (F9)"))

    # files
    def new_file(self):
        self.actions, self.path = [], None
        self.refresh()
        self.status.set(tr("Nouvelle macro"))

    def open_file(self):
        p = filedialog.askopenfilename(filetypes=[(tr("Macro ReMouse"), "*.rms"), (tr("Tous"), "*.*")])
        if p:
            self.load_path(p)

    def load_path(self, p: str):
        """Load a .rms file into the editor (also used for a file passed on the command line)."""
        try:
            self.actions, self.path = rms.load(p), p
        except OSError as e:
            messagebox.showerror(tr("Erreur"), str(e))
            return
        self.refresh()
        self.status.set(tr("%s : %d actions", p, len(self.actions)))

    def save_file(self):
        if not self.path:
            return self.save_file_as()
        try:
            rms.save(self.path, self.actions)
        except OSError as e:
            messagebox.showerror(tr("Erreur"), str(e))
            return
        self.status.set(tr("Enregistré : ") + self.path)

    def save_file_as(self):
        p = filedialog.asksaveasfilename(defaultextension=".rms", filetypes=[(tr("Macro ReMouse"), "*.rms")])
        if p:
            self.path = p
            self.save_file()

    # --------------------------------------------------------- tasks tab
    def _build_tasks(self):
        f = self.tab_tasks
        bar = ttk.Frame(f, padding=6)
        bar.pack(fill="x")
        for text, cmd in ((tr("Ajouter"), self.add_task), (tr("Modifier"), self.edit_task),
                          (tr("Supprimer"), self.delete_task), (tr("Lancer maintenant"), self.run_task_now)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        cols = ("on", "name", "path", "hotkey", "sched", "trig")
        self.ttree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
        for c, t, w in (("on", "Actif", 50), ("name", "Nom", 120), ("path", "Macro", 190),
                        ("hotkey", "Raccourci", 100), ("sched", "Planification", 150), ("trig", "Déclencheur", 140)):
            self.ttree.heading(c, text=tr(t))
            self.ttree.column(c, width=w)
        self.ttree.pack(fill="both", expand=True, padx=6, pady=6)
        self.ttree.bind("<Double-1>", lambda e: self.edit_task())
        ttk.Label(f, padding=6, foreground="gray",
                  text=tr("Les raccourcis, planifications et déclencheurs ne fonctionnent que tant qu'OpenReMouse est ouvert "
                          "(vous pouvez réduire la fenêtre).")).pack(fill="x")
        self.refresh_tasks()

    def refresh_tasks(self):
        sel = self.ttree.selection()
        self.ttree.delete(*self.ttree.get_children())
        for i, t in enumerate(self.mgr.tasks):
            s, g = tasks.describe(t)
            self.ttree.insert("", "end", iid=str(i), values=(tr("oui") if t.enabled else tr("non"), t.name, t.path,
                                                              t.hotkey, s, g))
        if sel and sel[0] in self.ttree.get_children():
            self.ttree.selection_set(sel[0])

    def _sel_task(self) -> int | None:
        s = self.ttree.selection()
        return int(s[0]) if s else None

    def _task_values(self, t: tasks.Task) -> dict:
        return {k: ("1" if v is True else "0" if v is False else str(v)) for k, v in vars(t).items()}

    def _edit_task_dialog(self, t: tasks.Task) -> tasks.Task | None:
        d = FormDialog(self.root, "Tâche", TASK_FIELDS, self._task_values(t)).result
        if d is None:
            return None
        return tasks.Task(name=d["name"] or tr("Tâche"), path=d["path"], hotkey=d["hotkey"],
                          repeat=int(d["repeat"]), speed=float(d["speed"]), schedule=d["schedule"],
                          at=d["at"], every=int(d["every"]), trigger=d["trigger"],
                          trigger_data=d["trigger_data"], enabled=d["enabled"] == "1")

    def _tasks_changed(self):
        tasks.save_tasks(self.mgr.tasks)
        self.rebuild_hotkeys()
        self.refresh_tasks()

    def add_task(self):
        t = tasks.Task(path=self.path or "")
        new = self._edit_task_dialog(t)
        if new:
            self.mgr.tasks.append(new)
            self._tasks_changed()

    def edit_task(self):
        i = self._sel_task()
        if i is None:
            return
        new = self._edit_task_dialog(self.mgr.tasks[i])
        if new:
            self.mgr.tasks[i] = new
            self._tasks_changed()

    def delete_task(self):
        i = self._sel_task()
        if i is not None:
            del self.mgr.tasks[i]
            self._tasks_changed()

    def run_task_now(self):
        i = self._sel_task()
        if i is not None:
            self._fire(self.mgr.tasks[i])

    # -------------------------------------------------------------- exit
    def close(self):
        if self.mgr.tasks:                        # a one-shot task may have switched itself off
            tasks.save_tasks(self.mgr.tasks)
        if self.hotkeys:
            self.hotkeys.stop()
        if self.recorder:
            self.recorder.stop()
        self.mgr.shutdown()
        self.root.destroy()


def _icon_path() -> str | None:
    base = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(__file__), ".."))   # PyInstaller / source
    p = os.path.join(base, "assets", "icon.ico")
    return p if os.path.exists(p) else None


def main():
    _dpi_aware()
    i18n.set_lang(i18n.load_pref(), save=False)       # saved choice, else the Windows display language
    root = tk.Tk()
    ico = _icon_path()
    if ico:
        try:
            root.iconbitmap(default=ico)          # also applies to every dialog
        except tk.TclError:
            pass
    app = App(root)
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):     # double-clicked / "Open with" .rms file
        app.load_path(os.path.abspath(sys.argv[1]))
    root.mainloop()
