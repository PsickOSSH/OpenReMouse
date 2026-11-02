import pathlib
import tempfile
import time
import unittest
from datetime import datetime

from openremouse import hotkeys, tasks
from openremouse.tasks import Task, schedule_due


def ts(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M").timestamp()


class TaskTests(unittest.TestCase):
    def test_hotkey_parsing_is_layout_independent(self):
        self.assertEqual(hotkeys.parse("Ctrl+Alt+1"), (frozenset({"ctrl", "alt"}), 0x31))
        self.assertEqual(hotkeys.parse("f9"), (frozenset(), 0x78))
        self.assertEqual(hotkeys.parse("shift+a"), (frozenset({"shift"}), 0x41))
        self.assertEqual(hotkeys.parse("ctrl+num5"), (frozenset({"ctrl"}), 0x65))
        for bad in ("", "ctrl", "ctrl+a+b", "ctrl+notakey"):
            with self.assertRaises(ValueError, msg=bad):
                hotkeys.parse(bad)

    def test_hotkey_matching_state_machine(self):
        from pynput.keyboard import Key, KeyCode
        hits = []
        h = hotkeys.Hotkeys({"ctrl+alt+1": lambda: hits.append("A"), "f9": lambda: hits.append("F9"),
                             "ctrl+alt+2": lambda: hits.append("B")}, key_state=lambda vk: True)
        press = lambda k: h._press(k)
        release = lambda k: h._release(k)
        digit1 = KeyCode.from_vk(0x31, char="&")          # AZERTY: the '1' key types '&'
        press(Key.f9); release(Key.f9)
        press(Key.ctrl_l); press(Key.f9); release(Key.f9); release(Key.ctrl_l)   # ctrl+f9 is not f9
        press(Key.ctrl_l); press(Key.alt_l); press(digit1); press(digit1)        # held: auto-repeat
        release(digit1); press(KeyCode.from_vk(0x32, char="é"))
        release(KeyCode.from_vk(0x32)); release(Key.alt_l); release(Key.ctrl_l)
        press(digit1); release(digit1)                                           # no modifiers: nothing
        # AltGr reports as ctrl + right-alt
        press(Key.ctrl_l); press(Key.alt_gr); press(digit1)
        self.assertEqual(hits, ["F9", "A", "B", "A"])

    def test_stuck_modifier_is_dropped(self):
        from pynput.keyboard import Key
        hits = []
        h = hotkeys.Hotkeys({"f9": lambda: hits.append("F9")}, key_state=lambda vk: False)
        h._press(Key.ctrl_l)                       # its key-up is never seen
        h._press(Key.f9)                           # but the OS says ctrl is up -> plain F9
        self.assertEqual(hits, ["F9"])

    def test_interval(self):
        t = Task(schedule="interval", every=60)
        now = datetime(2026, 1, 1, 12, 0, 0)
        self.assertFalse(schedule_due(t, now, 0, now.timestamp() - 59))
        self.assertTrue(schedule_due(t, now, 0, now.timestamp() - 60))
        self.assertFalse(schedule_due(t, now, now.timestamp() - 10, 0))

    def test_daily(self):
        t = Task(schedule="daily", at="09:00")
        started = ts("2026-01-01 08:00")
        self.assertFalse(schedule_due(t, datetime(2026, 1, 1, 8, 59), 0, started))
        self.assertTrue(schedule_due(t, datetime(2026, 1, 1, 9, 0), 0, started))
        # already ran today
        self.assertFalse(schedule_due(t, datetime(2026, 1, 1, 9, 5), ts("2026-01-01 09:00"), started))
        # next day it is due again
        self.assertTrue(schedule_due(t, datetime(2026, 1, 2, 9, 1), ts("2026-01-01 09:00"), started))
        # app launched after 9:00 must not replay this morning's run
        self.assertFalse(schedule_due(t, datetime(2026, 1, 1, 15, 0), 0, ts("2026-01-01 14:00")))

    def test_once(self):
        t = Task(schedule="once", at="2026-03-05 10:30")
        started = ts("2026-03-05 10:00")
        self.assertFalse(schedule_due(t, datetime(2026, 3, 5, 10, 29), 0, started))
        self.assertTrue(schedule_due(t, datetime(2026, 3, 5, 10, 30), 0, started))
        self.assertFalse(schedule_due(t, datetime(2026, 3, 5, 10, 31), ts("2026-03-05 10:30"), started))

    def test_bad_values_never_fire(self):
        for t in (Task(schedule="daily", at="nope"), Task(schedule="once", at=""), Task(schedule="off")):
            self.assertFalse(schedule_due(t, datetime.now(), 0, 0))

    def test_save_load_roundtrip_ignores_unknown_keys(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d, "t.json")
            tasks.save_tasks([Task(name="a", hotkey="f5", every=5, enabled=False)], p)
            raw = p.read_text(encoding="utf-8").replace('"name"', '"future_field": 1, "name"')
            p.write_text(raw, encoding="utf-8")
            (t,) = tasks.load_tasks(p)
            self.assertEqual((t.name, t.hotkey, t.every, t.enabled), ("a", "f5", 5, False))
            self.assertEqual(tasks.load_tasks(pathlib.Path(d, "missing.json")), [])

    def test_manager_runs_one_macro_at_a_time_and_scheduler_fires(self):
        from openremouse import rms
        with tempfile.TemporaryDirectory() as d:
            macro = pathlib.Path(d, "m.rms")
            macro.write_text("{Delay 0.4}\r\n", encoding="utf-8")
            events = []
            m = tasks.TaskManager(on_event=events.append)
            self.assertTrue(m.run(rms.load(str(macro)), label="x"))
            self.assertFalse(m.run(rms.load(str(macro)), label="y"))      # busy
            time.sleep(0.8)
            self.assertFalse(m.busy)
            self.assertTrue(any(e.startswith("Terminé") for e in events))

            events.clear()
            m.tasks = [Task(name="tick", path=str(macro), schedule="interval", every=1)]
            m._started = time.time() - 5
            m.start()
            time.sleep(2.5)
            m.shutdown()
            self.assertTrue(any(e.startswith("Lancé : tick") for e in events), events)


if __name__ == "__main__":
    unittest.main()
