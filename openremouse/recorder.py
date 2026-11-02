"""Record mouse / keyboard events into a list of rms Actions."""
from __future__ import annotations

import time

from pynput import keyboard, mouse

from . import keys
from .rms import Action

_BTN = {mouse.Button.left: "LMouse", mouse.Button.right: "RMouse", mouse.Button.middle: "MMouse"}


class Recorder:
    def __init__(self, record_moves=True, record_clicks=True, record_keys=True,
                 record_delays=True, ignore_keys=("F9", "F10"), ignore_area=None):
        # ignore_area() -> (x0, y0, x1, y1) screen rect whose clicks are not recorded (the Record button)
        self.ignore_area = ignore_area
        self.record_moves, self.record_clicks = record_moves, record_clicks
        self.record_keys, self.record_delays = record_keys, record_delays
        self.ignore_keys = {k.upper() for k in ignore_keys}
        self._events: list[tuple[float, Action]] = []
        self._listeners: list = []

    def start(self):
        self._events.clear()
        self._listeners = [
            mouse.Listener(on_move=self._on_move, on_click=self._on_click),
            keyboard.Listener(on_press=lambda k: self._on_key(k, True),
                              on_release=lambda k: self._on_key(k, False)),
        ]
        for l in self._listeners:
            l.start()

    def stop(self) -> list[Action]:
        for l in self._listeners:
            l.stop()
        self._listeners = []
        return self._build()

    def _add(self, a: Action):
        self._events.append((time.perf_counter(), a))

    def _on_move(self, x, y):
        if self.record_moves:
            self._add(Action("moves", moves=[(0.0, int(x), int(y))]))

    def _on_click(self, x, y, button, pressed):
        if self._ignored(x, y):
            return
        if self.record_clicks and button in _BTN:
            self._add(Action("mouse", button=_BTN[button], pressed=pressed, x=int(x), y=int(y)))

    def _ignored(self, x, y) -> bool:
        if not self.ignore_area:
            return False
        try:
            x0, y0, x1, y1 = self.ignore_area()
        except Exception:
            return False
        return x0 <= x < x1 and y0 <= y < y1

    def _on_key(self, key, pressed):
        name = keys.to_name(key)
        if not self.record_keys or name is None or name.upper() in self.ignore_keys:
            return
        # drop auto-repeat: ignore a press if this key's last recorded event was also a press
        for _, a in reversed(self._events):
            if a.kind == "key" and a.key == name:
                if a.pressed == pressed:
                    return
                break
        self._add(Action("key", pressed=pressed, key=name))

    def _build(self) -> list[Action]:
        out: list[Action] = []
        prev_t = self._events[0][0] if self._events else 0.0
        for t, a in self._events:
            gap = round(t - prev_t, 2) if self.record_delays else 0.0
            prev_t = t
            if a.kind == "moves":
                sample = (gap, a.moves[0][1], a.moves[0][2])
                if out and out[-1].kind == "moves":
                    out[-1].moves.append(sample)
                else:
                    out.append(Action("moves", moves=[sample]))
            else:
                if gap >= 0.01:
                    out.append(Action("delay", delay=gap))
                out.append(a)
        return out
