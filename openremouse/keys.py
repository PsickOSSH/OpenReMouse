"""Key name <-> pynput key mapping."""
from __future__ import annotations

from pynput.keyboard import Key, KeyCode

_SPECIAL = {
    "BACKSPACE": Key.backspace, "TAB": Key.tab, "ENTER": Key.enter, "SHIFT": Key.shift,
    "CTRL": Key.ctrl, "ALT": Key.alt, "PAUSE": Key.pause, "CAPSLOCK": Key.caps_lock,
    "ESC": Key.esc, "SPACE": Key.space, "PGUP": Key.page_up, "PGDN": Key.page_down,
    "END": Key.end, "HOME": Key.home, "LEFT": Key.left, "UP": Key.up, "RIGHT": Key.right,
    "DOWN": Key.down, "INSERT": Key.insert, "DEL": Key.delete, "LWIN": Key.cmd_l,
    "RWIN": Key.cmd_r, "APPSKEY": Key.menu, "NUMLOCK": Key.num_lock,
    "PRINTSCREEN": Key.print_screen,
}
for _i in range(1, 25):
    _SPECIAL["F%d" % _i] = getattr(Key, "f%d" % _i)
_REVERSE = {v: k for k, v in _SPECIAL.items()}
# left/right variants map to the generic names
for _k, _n in ((Key.shift_l, "SHIFT"), (Key.shift_r, "SHIFT"), (Key.ctrl_l, "CTRL"),
               (Key.ctrl_r, "CTRL"), (Key.alt_l, "ALT"), (Key.alt_r, "ALT"),
               (Key.alt_gr, "ALT")):
    _REVERSE[_k] = _n


def to_name(key) -> str | None:
    if key in _REVERSE:
        return _REVERSE[key]
    if isinstance(key, KeyCode):
        if key.char and key.char.isprintable():
            return key.char.lower()
        if key.vk is not None:
            return "VK%d" % key.vk
    return None


def from_name(name: str):
    if name.upper() in _SPECIAL:
        return _SPECIAL[name.upper()]
    if name.upper().startswith("VK") and name[2:].isdigit():
        return KeyCode.from_vk(int(name[2:]))
    if len(name) == 1:
        return KeyCode.from_char(name)
    return None
