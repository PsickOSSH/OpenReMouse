"""Global hotkeys matched on Windows virtual-key codes, so they work on any keyboard layout.

(pynput's own GlobalHotKeys compares characters: on AZERTY, Ctrl+Alt+7 yields AltGr+7 = 'è',
and the digit row needs Shift, so "ctrl+alt+1" would never match.)
"""
from __future__ import annotations

import ctypes

from pynput import keyboard

_MODS = {"ctrl": "ctrl", "control": "ctrl", "alt": "alt", "shift": "shift", "win": "win", "cmd": "win"}
_MOD_VKS = {0x10: "shift", 0xA0: "shift", 0xA1: "shift", 0x11: "ctrl", 0xA2: "ctrl", 0xA3: "ctrl",
            0x12: "alt", 0xA4: "alt", 0xA5: "alt", 0x5B: "win", 0x5C: "win"}
_NAMED = {"space": 0x20, "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B, "tab": 0x09,
          "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23,
          "pageup": 0x21, "pgup": 0x21, "pagedown": 0x22, "pgdn": 0x22, "left": 0x25, "up": 0x26,
          "right": 0x27, "down": 0x28, "pause": 0x13, "printscreen": 0x2C, "capslock": 0x14,
          "numlock": 0x90, "scrolllock": 0x91}
for _i in range(1, 25):
    _NAMED["f%d" % _i] = 0x70 + _i - 1
for _i in range(10):
    _NAMED["num%d" % _i] = 0x60 + _i          # numeric keypad


def parse(spec: str) -> tuple[frozenset, int]:
    """'ctrl+alt+1' -> (frozenset({'ctrl', 'alt'}), 0x31). Raises ValueError if invalid."""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    mods, main = set(), None
    for p in parts:
        if p in _MODS:
            mods.add(_MODS[p])
        elif main is not None:
            raise ValueError("une seule touche principale autorisée : %r" % spec)
        elif p in _NAMED:
            main = _NAMED[p]
        elif len(p) == 1 and p.isalnum() and p.isascii():
            main = ord(p.upper())                  # VK_A..VK_Z and VK_0..VK_9 equal their ASCII codes
        elif len(p) == 1:
            r = ctypes.windll.user32.VkKeyScanW(ctypes.c_wchar(p))
            if r == -1:
                raise ValueError("touche inconnue : %r" % p)
            main = r & 0xFF
        else:
            raise ValueError("touche inconnue : %r" % p)
    if main is None:
        raise ValueError("aucune touche principale : %r" % spec)
    return frozenset(mods), main


def _vk(key) -> int | None:
    if isinstance(key, keyboard.Key):
        key = key.value
    return getattr(key, "vk", None)


def _async_down(vk: int) -> bool:
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


class Hotkeys:
    """``Hotkeys({'ctrl+alt+1': callback, ...})``; callbacks run on the listener thread."""

    def __init__(self, mapping: dict, key_state=None):
        # key_state(vk) -> is that key physically down? Used to drop modifiers whose release we missed.
        self._key_state = key_state or _async_down
        self._table: dict[tuple, object] = {}
        for spec, cb in mapping.items():
            self._table.setdefault(parse(spec), cb)    # first definition of a combo wins
        self._mods: set[str] = set()
        self._down: set[int] = set()
        self._listener = keyboard.Listener(on_press=self._press, on_release=self._release)

    def start(self):
        self._listener.start()

    def stop(self):
        self._listener.stop()

    def _press(self, key):
        vk = _vk(key)
        if vk is None:
            return
        if vk in _MOD_VKS:
            self._mods.add(_MOD_VKS[vk])
            return
        if vk in self._down:                           # key auto-repeat
            return
        self._down.add(vk)
        self._resync_mods()
        cb = self._table.get((frozenset(self._mods), vk))
        if cb:
            cb()

    def _resync_mods(self):
        """A missed key-up (Win+L, secure desktop...) would leave a modifier stuck: re-check the real state."""
        for m in list(self._mods):
            if not any(self._key_state(vk) for vk, name in _MOD_VKS.items() if name == m):
                self._mods.discard(m)

    def _release(self, key):
        vk = _vk(key)
        if vk in _MOD_VKS:
            self._mods.discard(_MOD_VKS[vk])
        else:
            self._down.discard(vk)
