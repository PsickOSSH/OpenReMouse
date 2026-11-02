"""Tasks: a macro + optional hotkey, schedule and trigger. Plus the runner."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path

from . import actions as extra
from . import rms, winapi
from .i18n import tr
from .settings import CONFIG_DIR
from .player import Player

TASKS_FILE = CONFIG_DIR / "tasks.json"

SCHEDULES = ("off", "once", "daily", "interval")
TRIGGERS = ("off", "window", "process")


@dataclass
class Task:
    name: str = "Nouvelle tâche"
    path: str = ""                  # .rms file
    hotkey: str = ""                # e.g. "ctrl+alt+1"
    repeat: int = 1
    speed: float = 1.0
    schedule: str = "off"           # off | once | daily | interval
    at: str = ""                    # once: "YYYY-MM-DD HH:MM"   daily: "HH:MM"
    every: int = 60                 # interval: seconds
    trigger: str = "off"            # off | window | process (fires when it appears)
    trigger_data: str = ""          # window title / process name
    enabled: bool = True


def load_tasks(path: Path = TASKS_FILE) -> list[Task]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    names = {f.name for f in fields(Task)}
    return [Task(**{k: v for k, v in d.items() if k in names}) for d in raw if isinstance(d, dict)]


def save_tasks(tasks: list[Task], path: Path = TASKS_FILE) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(t) for t in tasks], indent=2, ensure_ascii=False), encoding="utf-8")


def schedule_due(t: Task, now: datetime, last_run: float, started: float) -> bool:
    """Is a scheduled task due? ``last_run`` / ``started`` are epoch seconds (0 = never).

    A fixed time (once / daily) only fires if the app was already running before that
    time, so launching the app late in the day never replays the morning's task.
    """
    ref = max(last_run, started)
    try:
        if t.schedule == "interval":
            return t.every > 0 and now.timestamp() - ref >= t.every
        if t.schedule == "daily":
            hh, mm = (int(x) for x in t.at.split(":"))
            target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        elif t.schedule == "once":
            target = datetime.strptime(t.at.strip(), "%Y-%m-%d %H:%M")
        else:
            return False
    except ValueError:
        return False
    return now >= target and ref < target.timestamp()


def trigger_active(t: Task) -> bool:
    d = t.trigger_data.strip()
    if not d:
        return False
    if t.trigger == "window":
        return winapi.find_window(d) is not None
    if t.trigger == "process":
        return extra.process_running(d)
    return False


def describe(t: Task) -> tuple[str, str]:
    s = {"off": "", "once": tr("une fois, ") + t.at, "daily": tr("chaque jour à ") + t.at,
         "interval": tr("toutes les %d s", t.every)}[t.schedule]
    g = {"off": "", "window": tr("fenêtre « %s »", t.trigger_data),
         "process": tr("processus %s", t.trigger_data)}[t.trigger]
    return s, g


class TaskManager:
    """Runs one macro at a time, and watches schedules / triggers in a background thread."""

    def __init__(self, on_event=lambda msg: None):
        self.tasks: list[Task] = []
        self.on_event = on_event
        self.player: Player | None = None
        self.current_task: Task | None = None     # the task being played (None for a plain macro)
        self._lock = threading.Lock()
        self._halt = threading.Event()
        self._started = time.time()
        self._last: dict[int, float] = {}
        self._prev: dict[int, bool] = {}
        self._thread: threading.Thread | None = None

    @property
    def busy(self) -> bool:
        return self.player is not None

    def run(self, actions: list, repeat=1, speed=1.0, label="macro", on_done=None, task=None) -> bool:
        with self._lock:
            if self.player:
                return False
            p = self.player = Player(speed)
            self.current_task = task

        def work():
            try:
                p.play(actions, repeat)
            finally:
                with self._lock:
                    self.player = None
                    self.current_task = None
                self.on_event(tr("Erreur (%s) : %s", label, p.error) if p.error else
                              tr("Terminé : %s", label))
                if on_done:
                    on_done()

        threading.Thread(target=work, daemon=True).start()
        return True

    def run_task(self, t: Task) -> bool:
        try:
            acts = rms.load(t.path)
        except OSError as e:
            self.on_event(tr("Erreur (%s) : %s", t.name, e))
            return False
        ok = self.run(acts, t.repeat, t.speed, t.name, task=t)
        if ok:
            self._last[id(t)] = time.time()
            self.on_event(tr("Lancé : %s", t.name))
        else:
            self.on_event(tr("Occupé : « %s » ignorée (une macro tourne déjà)", t.name))
        return ok

    def stop(self):
        p = self.player
        if p:
            p.stop()

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def shutdown(self):
        self._halt.set()
        self.stop()

    def _loop(self):
        while not self._halt.wait(1.0):
            now = datetime.now()
            for t in list(self.tasks):
                if not t.enabled or not t.path:
                    continue
                key = id(t)
                fire = False
                if t.schedule != "off" and schedule_due(t, now, self._last.get(key, 0.0), self._started):
                    fire = True
                if t.trigger != "off":
                    cur = trigger_active(t)
                    fire = fire or (cur and not self._prev.get(key, cur))   # rising edge only
                    self._prev[key] = cur
                if fire:
                    # Count the attempt even if it fails (busy / missing file): otherwise a due task
                    # would be retried and report an error every second.
                    self._last[key] = time.time()
                    if self.run_task(t) and t.schedule == "once":
                        t.enabled = False    # a one-shot task fires once, then switches itself off
