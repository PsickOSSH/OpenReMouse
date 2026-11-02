"""Reading / writing of the plain-text ``.rms`` macro format.

One action per ``{...}`` block, e.g.::

    {Delay 0.50}
    {RMouse down (225,202)}
    {RMouse up (225,202)}
    {Movements (0.36:226:192|0.05:254:192)}   # delay:x:y samples
    {Key down a}                              # keyboard syntax is our own choice
    {WaitColor x=100 y=200 color=FF0000}      # extended actions: Name key=value ...
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

BUTTONS = ("LMouse", "RMouse", "MMouse")

_DELAY = re.compile(r"^Delay\s+([0-9.]+)$", re.I)
_MOUSE = re.compile(r"^(LMouse|RMouse|MMouse)\s+(down|up)\s*\((-?\d+),\s*(-?\d+)\)$", re.I)
_MOVES = re.compile(r"^Movements\s*\((.*)\)$", re.I)
_KEY = re.compile(r"^Key\s+(down|up)\s+(.+)$", re.I)
_VALUE = r'(?:"(?:[^"\\]|\\.)*"|\S*)'
_CMD = re.compile(r"^[A-Za-z]\w*(?:\s+\w+=" + _VALUE + r")*$")
_ARG = re.compile(r"(\w+)=(" + _VALUE + r")")
_ESC = {"n": "\n", "r": "\r", "t": "\t"}


def _quote(v: str) -> str:
    if v and not re.search(r'[\s"\\]', v):
        return v
    v = v.replace("\\", "\\\\").replace('"', '\\"')
    v = v.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return '"%s"' % v


def _unquote(v: str) -> str:
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return re.sub(r"\\(.)", lambda m: _ESC.get(m.group(1), m.group(1)), v[1:-1])
    return v


@dataclass
class Action:
    kind: str                       # delay | mouse | moves | key | cmd | raw
    delay: float = 0.0              # delay
    button: str = ""                # mouse
    pressed: bool = False           # mouse / key
    x: int = 0                      # mouse
    y: int = 0                      # mouse
    moves: list = field(default_factory=list)   # [(delay, x, y)]
    key: str = ""                   # key
    name: str = ""                  # cmd: action name
    args: dict = field(default_factory=dict)    # cmd: str -> str
    raw: str = ""                   # unknown line, kept verbatim

    def to_line(self) -> str:
        if self.kind == "delay":
            return "{Delay %.2f}" % self.delay
        if self.kind == "mouse":
            return "{%s %s (%d,%d)}" % (self.button, "down" if self.pressed else "up", self.x, self.y)
        if self.kind == "moves":
            return "{Movements (%s)}" % "|".join("%.2f:%d:%d" % m for m in self.moves)
        if self.kind == "key":
            return "{Key %s %s}" % ("down" if self.pressed else "up", self.key)
        if self.kind == "cmd":
            return "{%s}" % " ".join([self.name] + ["%s=%s" % (k, _quote(str(v))) for k, v in self.args.items()])
        return self.raw


def parse_line(line: str) -> Action | None:
    line = line.strip()
    if not line:
        return None
    if not (line.startswith("{") and line.endswith("}")):
        return Action("raw", raw=line)
    body = line[1:-1].strip()
    if (g := _DELAY.match(body)):
        return Action("delay", delay=float(g.group(1)))
    if (g := _MOUSE.match(body)):
        b = next(x for x in BUTTONS if x.lower() == g.group(1).lower())
        return Action("mouse", button=b, pressed=g.group(2).lower() == "down",
                      x=int(g.group(3)), y=int(g.group(4)))
    if (g := _MOVES.match(body)):
        try:
            moves = []
            for s in filter(None, g.group(1).split("|")):
                d, x, y = s.split(":")
                moves.append((float(d), int(x), int(y)))
            return Action("moves", moves=moves)
        except ValueError:
            return Action("raw", raw=line)
    if (g := _KEY.match(body)):
        return Action("key", pressed=g.group(1).lower() == "down", key=g.group(2).strip())
    if _CMD.match(body):
        name = body.split(None, 1)[0]
        return Action("cmd", name=name, args={k: _unquote(v) for k, v in _ARG.findall(body)})
    return Action("raw", raw=line)


def loads(text: str) -> list[Action]:
    # not str.splitlines(): it also splits on exotic separators that may appear in values
    return [a for a in map(parse_line, text.split("\n")) if a]


def dumps(actions: list[Action]) -> str:
    return "\r\n".join(a.to_line() for a in actions) + "\r\n"


def load(path: str) -> list[Action]:
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return loads(f.read())


def save(path: str, actions: list[Action]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(dumps(actions))
