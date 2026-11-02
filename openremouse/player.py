"""Play back a list of rms Actions."""
from __future__ import annotations

import threading

from pynput import keyboard, mouse

from . import actions as extra
from . import keys
from .i18n import tr
from .rms import Action

_BTN = {"LMouse": mouse.Button.left, "RMouse": mouse.Button.right, "MMouse": mouse.Button.middle}


class Player:
    def __init__(self, speed: float = 1.0):
        self.speed = max(speed, 0.01)
        self._stop = threading.Event()
        self.mouse = mouse.Controller()
        self.kb = keyboard.Controller()
        self._held_keys: set = set()
        self._held_buttons: set = set()
        self.error: str | None = None

    # -- context API used by extended actions
    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def wait(self, seconds: float) -> bool:
        """Interruptible wait (not scaled by speed); returns False if stopped."""
        if seconds > 0:
            self._stop.wait(seconds)
        return not self._stop.is_set()

    def stop(self):
        self._stop.set()

    def _sleep(self, seconds: float) -> bool:
        return self.wait(seconds / self.speed)

    def play(self, actions: list[Action], repeat: int = 1, pause_between: float = 0.0,
             on_done=None):
        """Play ``actions`` ``repeat`` times (0 = until stop()). Sets ``self.error`` on failure."""
        self._stop.clear()
        self.error = None
        try:
            n = 0
            while not self._stop.is_set() and (repeat == 0 or n < repeat):
                for a in actions:
                    if not self._do(a):
                        return
                n += 1
                if not self._sleep(pause_between):
                    return
        finally:
            self._release_all()
            if on_done:
                on_done()

    def _do(self, a: Action) -> bool:
        if a.kind == "delay":
            return self._sleep(a.delay)
        if a.kind == "moves":
            for d, x, y in a.moves:
                if not self._sleep(d):
                    return False
                self.mouse.position = (x, y)
            return True
        if a.kind == "mouse":
            self.mouse.position = (a.x, a.y)
            btn = _BTN[a.button]
            if a.pressed:
                self.mouse.press(btn)
                self._held_buttons.add(btn)
            else:
                self.mouse.release(btn)
                self._held_buttons.discard(btn)
        elif a.kind == "key":
            k = keys.from_name(a.key)
            if k is not None:
                if a.pressed:
                    self.kb.press(k)
                    self._held_keys.add(k)
                else:
                    self.kb.release(k)
                    self._held_keys.discard(k)
        elif a.kind == "cmd":
            spec = extra.REGISTRY.get(a.name)
            if spec is None:
                self.error = tr("action inconnue : %s", a.name)
                return False
            try:
                if not spec.run(a.args, self):
                    return False
            except Exception as e:          # a failing step stops the macro: later steps may depend on it
                self.error = "%s : %s" % (a.name, e)
                return False
        # "raw" (unknown) lines are skipped
        return not self._stop.is_set()

    def _release_all(self):
        """Never leave a key or button stuck after stopping mid-macro."""
        for k in list(self._held_keys):
            self.kb.release(k)
        for b in list(self._held_buttons):
            self.mouse.release(b)
        self._held_keys.clear()
        self._held_buttons.clear()
