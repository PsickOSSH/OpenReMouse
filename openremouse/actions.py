"""Registry of the extended macro actions ({Name key=value ...} lines in .rms files).

Each action is ``run(args: dict[str, str], ctx) -> bool``. ``ctx`` is the Player
(``ctx.kb`` keyboard controller, ``ctx.stopped``, ``ctx.wait(seconds)``).
Return False to stop the macro quietly; raise to stop it with an error message.
"""
from __future__ import annotations

import csv
import io
import os
import shlex
import shutil
import socket
import subprocess
import time
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from typing import Callable

from . import keys, winapi
from .i18n import tr

_NO_WINDOW = 0x08000000


@dataclass
class Field:
    key: str
    label: str
    kind: str = "str"            # str | int | float | choice | file | bool
    default: str = ""
    choices: tuple = ()


@dataclass
class Spec:
    name: str
    label: str
    category: str
    fields: list = field(default_factory=list)
    run: Callable = None
    pick: str = ""               # "point": editor offers "aim at screen" filling x / y / color


REGISTRY: dict[str, Spec] = {}


def register(name, label, category, fields=(), pick=""):
    def deco(fn):
        REGISTRY[name] = Spec(name, label, category, list(fields), fn, pick)
        return fn
    return deco


TIMEOUT = Field("timeout", "Délai max en secondes (0 = sans limite)", "float", "30")
ON_TIMEOUT = Field("on_timeout", "Si le délai est dépassé", "choice", "stop", ("stop", "continue"))


# ---------------------------------------------------------------- helpers
def _f(a, k, d=0.0):
    try:
        return float(a.get(k, d))
    except (TypeError, ValueError):
        return float(d)


def _i(a, k, d=0):
    return int(_f(a, k, d))


def _wait_for(ctx, cond, timeout, interval=0.2) -> str:
    end = time.monotonic() + timeout if timeout > 0 else None
    while True:
        if ctx.stopped:
            return "stopped"
        if cond():
            return "ok"
        if end is not None and time.monotonic() >= end:
            return "timeout"
        ctx.wait(interval)


def _result(r: str, a) -> bool:
    if r == "stopped":
        return False
    if r == "timeout":
        return a.get("on_timeout", "stop") == "continue"
    return True


def parse_color(s: str) -> tuple[int, int, int]:
    s = s.strip().lstrip("#")
    if s.lower().startswith("0x"):
        s = s[2:]
    if len(s) != 6:
        raise ValueError(tr("couleur attendue au format RRGGBB : %r", s))
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _need(h, what: str, pattern: str):
    if not h:
        raise RuntimeError(tr("%s introuvable : %r", tr(what), pattern))
    return h


def _processes() -> set[str]:
    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True,
                         errors="replace", creationflags=_NO_WINDOW).stdout
    return {row[0].lower() for row in csv.reader(io.StringIO(out)) if row}


def _exe(name: str) -> str:
    name = name.strip().lower()
    return name if name.endswith(".exe") or "." in name else name + ".exe"


def process_running(name: str) -> bool:
    return _exe(name) in _processes()


# ------------------------------------------------------------------ color
@register("WaitColor", "Attendre une couleur", "Couleur", [
    Field("x", "X", "int", "0"), Field("y", "Y", "int", "0"),
    Field("color", "Couleur (RRGGBB)", "str", "FF0000"),
    Field("tolerance", "Tolérance (0-255)", "int", "10"),
    Field("until", "Attendre que la couleur soit", "choice", "present", ("present", "absent")),
    TIMEOUT, ON_TIMEOUT], pick="point")
def _wait_color(a, ctx):
    x, y, tol = _i(a, "x"), _i(a, "y"), _i(a, "tolerance", 10)
    target = parse_color(a.get("color", "000000"))
    want = a.get("until", "present") == "present"

    def match():
        p = winapi.get_pixel(x, y)
        return p is not None and all(abs(p[i] - target[i]) <= tol for i in range(3)) == want

    return _result(_wait_for(ctx, match, _f(a, "timeout", 30)), a)


# ---------------------------------------------------------------- windows
_WIN = Field("title", "Titre de la fenêtre (ou class:NomDeClasse)")


@register("WinActivate", "Activer une fenêtre", "Fenêtres", [_WIN])
def _win_activate(a, ctx):
    h = _need(winapi.find_window(a.get("title", "")), "Fenêtre", a.get("title"))
    winapi.activate(h)
    return True


@register("WinClose", "Fermer une fenêtre", "Fenêtres", [_WIN])
def _win_close(a, ctx):
    h = winapi.find_window(a.get("title", ""))
    if h:
        winapi.close(h)
    return True


@register("WinFlash", "Faire clignoter une fenêtre", "Fenêtres",
          [_WIN, Field("count", "Nombre de clignotements", "int", "3")])
def _win_flash(a, ctx):
    h = _need(winapi.find_window(a.get("title", "")), "Fenêtre", a.get("title"))
    winapi.flash(h, _i(a, "count", 3))
    return True


def _win_wait(name, label, cond):
    @register(name, label, "Fenêtres", [_WIN, TIMEOUT, ON_TIMEOUT])
    def run(a, ctx):
        t = a.get("title", "")
        return _result(_wait_for(ctx, lambda: cond(t), _f(a, "timeout", 30)), a)
    return run


_win_wait("WinWait", "Attendre l'ouverture d'une fenêtre", lambda t: winapi.find_window(t) is not None)
_win_wait("WinWaitActive", "Attendre qu'une fenêtre soit active", winapi.is_foreground)
_win_wait("WinWaitInactive", "Attendre qu'une fenêtre ne soit plus active", lambda t: not winapi.is_foreground(t))
_win_wait("WinWaitClose", "Attendre la fermeture d'une fenêtre", lambda t: winapi.find_window(t) is None)


# --------------------------------------------------------------- controls
_CTRL_FIELDS = [Field("window", "Titre de la fenêtre"),
                Field("control", "Texte du contrôle (ou class:Button)")]


def _control(name, label, op):
    @register(name, label, "Contrôles", _CTRL_FIELDS)
    def run(a, ctx):
        w = _need(winapi.find_window(a.get("window", "")), "Fenêtre", a.get("window"))
        c = _need(winapi.find_control(w, a.get("control", "")), "Contrôle", a.get("control"))
        op(c)
        return True
    return run


_control("ControlClick", "Cliquer sur un contrôle", winapi.control_click)
_control("ControlEnable", "Activer un contrôle", lambda c: winapi.control_enable(c, True))
_control("ControlDisable", "Désactiver un contrôle", lambda c: winapi.control_enable(c, False))
_control("ControlFocus", "Donner le focus à un contrôle", winapi.control_focus)
_control("ControlShow", "Afficher un contrôle", lambda c: winapi.control_show(c, True))
_control("ControlHide", "Masquer un contrôle", lambda c: winapi.control_show(c, False))


# ------------------------------------------------------------------ files
@register("CopyFile", "Copier un fichier", "Fichiers", [
    Field("src", "Source", "file"), Field("dst", "Destination (fichier ou dossier)", "file"),
    Field("overwrite", "Écraser si existe", "bool", "1")])
def _copy_file(a, ctx):
    src, dst = a.get("src", ""), a.get("dst", "")
    if os.path.isdir(dst):
        dst = os.path.join(dst, os.path.basename(src))
    if os.path.exists(dst) and a.get("overwrite", "1") not in ("1", "True", "true"):
        return True
    shutil.copy2(src, dst)
    return True


@register("DeleteFile", "Supprimer un fichier", "Fichiers", [Field("path", "Fichier", "file")])
def _delete_file(a, ctx):
    p = a.get("path", "")
    if os.path.isfile(p):
        os.remove(p)
    return True


@register("OpenFile", "Ouvrir un programme / fichier", "Fichiers", [
    Field("path", "Programme ou fichier", "file"), Field("args", "Arguments"),
    Field("wait", "Attendre la fin du programme", "bool", "0")])
def _open_file(a, ctx):
    p, args = a.get("path", ""), a.get("args", "")
    if not args and a.get("wait", "0") not in ("1", "True", "true"):
        os.startfile(p)
        return True
    proc = subprocess.Popen([p] + shlex.split(args, posix=False))
    if a.get("wait", "0") in ("1", "True", "true"):
        return _wait_for(ctx, lambda: proc.poll() is not None, 0) == "ok"
    return True


# --------------------------------------------------------------- internet
@register("OpenURL", "Ouvrir un site web", "Internet", [Field("url", "Adresse")])
def _open_url(a, ctx):
    url = a.get("url", "")
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        url = "https://" + url
    webbrowser.open(url)
    return True


@register("Download", "Télécharger un fichier", "Internet", [
    Field("url", "Adresse"), Field("dest", "Enregistrer dans (fichier ou dossier)", "file"),
    Field("timeout", "Délai réseau en secondes", "float", "30")])
def _download(a, ctx):
    url, dest = a.get("url", ""), a.get("dest", "")
    if os.path.isdir(dest):
        dest = os.path.join(dest, os.path.basename(urllib.parse.urlparse(url).path) or "download")
    tmp = dest + ".part"
    with urllib.request.urlopen(url, timeout=_f(a, "timeout", 30)) as r, open(tmp, "wb") as out:
        while not ctx.stopped:
            chunk = r.read(65536)
            if not chunk:
                break
            out.write(chunk)
    if ctx.stopped:
        os.remove(tmp)
        return False
    os.replace(tmp, dest)
    return True


@register("CheckInternet", "Vérifier la connexion internet", "Internet", [
    Field("host", "Serveur à joindre (port 443)", "str", "1.1.1.1"),
    Field("on_fail", "Si pas de connexion", "choice", "stop", ("stop", "continue"))])
def _check_internet(a, ctx):
    try:
        socket.create_connection((a.get("host", "1.1.1.1"), 443), timeout=5).close()
        return True
    except OSError:
        return a.get("on_fail", "stop") == "continue"


# ----------------------------------------------------------------- system
@register("MessageBox", "Afficher un message", "Système", [
    Field("text", "Message"), Field("title", "Titre", "str", "OpenReMouse")])
def _message_box(a, ctx):
    winapi.user32.MessageBoxW(None, a.get("text", ""), a.get("title", ""), 0x40040)  # info + topmost
    return not ctx.stopped


@register("KillProcess", "Terminer un processus", "Système", [Field("name", "Nom (ex. notepad.exe)")])
def _kill_process(a, ctx):
    subprocess.run(["taskkill", "/F", "/IM", _exe(a.get("name", ""))], capture_output=True,
                   creationflags=_NO_WINDOW)
    return True


@register("WaitProcess", "Attendre un processus", "Système", [
    Field("name", "Nom (ex. notepad.exe)"),
    Field("state", "Attendre qu'il soit", "choice", "exited", ("running", "exited")),
    TIMEOUT, ON_TIMEOUT])
def _wait_process(a, ctx):
    want = a.get("state", "exited") == "running"
    n = a.get("name", "")
    return _result(_wait_for(ctx, lambda: process_running(n) == want, _f(a, "timeout", 30), 0.5), a)


@register("Shutdown", "Éteindre / redémarrer", "Système", [
    Field("mode", "Action", "choice", "shutdown", ("shutdown", "restart", "logoff", "cancel")),
    Field("delay", "Délai avant exécution (s)", "int", "30")])
def _shutdown(a, ctx):
    d = str(max(_i(a, "delay", 30), 0))
    cmd = {"shutdown": ["shutdown", "/s", "/t", d], "restart": ["shutdown", "/r", "/t", d],
           "logoff": ["shutdown", "/l"], "cancel": ["shutdown", "/a"]}[a.get("mode", "shutdown")]
    subprocess.run(cmd, capture_output=True, creationflags=_NO_WINDOW)
    return True


# --------------------------------------------------------------- keyboard
@register("Keystroke", "Combinaison de touches", "Clavier", [
    Field("keys", "Touches (ex. ctrl+shift+s)")])
def _keystroke(a, ctx):
    parts = [p.strip() for p in a.get("keys", "").split("+") if p.strip()]
    ks = []
    for p in parts:
        k = keys.from_name(p)
        if k is None:
            raise RuntimeError(tr("touche inconnue : %r", p))
        ks.append(k)
    for k in ks:
        ctx.kb.press(k)
    for k in reversed(ks):
        ctx.kb.release(k)
    return True


@register("TypeText", "Saisir du texte", "Clavier", [
    Field("text", "Texte"), Field("interval", "Pause entre caractères (s)", "float", "0")])
def _type_text(a, ctx):
    text, iv = a.get("text", ""), _f(a, "interval", 0)
    if iv <= 0:
        ctx.kb.type(text)
        return True
    for ch in text:
        if ctx.stopped:
            return False
        ctx.kb.type(ch)
        ctx.wait(iv)
    return True


CATEGORIES = ["Clavier", "Couleur", "Fenêtres", "Contrôles", "Fichiers", "Internet", "Système"]
