import os
import pathlib
import tempfile
import threading
import time
import unittest
from unittest import mock

from openremouse import actions, i18n, rms, winapi
from openremouse.player import Player

i18n.set_lang("fr", save=False)      # these tests assert on French error messages


class Ctx:
    stopped = False

    def wait(self, s):
        time.sleep(min(s, 0.01))
        return True


def run(name, **args):
    return actions.REGISTRY[name].run({k: str(v) for k, v in args.items()}, Ctx())


class ActionTests(unittest.TestCase):
    def test_every_spec_has_unique_field_keys_and_known_category(self):
        for s in actions.REGISTRY.values():
            keys = [f.key for f in s.fields]
            self.assertEqual(len(keys), len(set(keys)), s.name)
            self.assertIn(s.category, actions.CATEGORIES, s.name)

    def test_files(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = os.path.join(d, "a.txt"), os.path.join(d, "b.txt")
            pathlib.Path(src).write_text("hello")
            run("CopyFile", src=src, dst=dst, overwrite=1)
            self.assertEqual(pathlib.Path(dst).read_text(), "hello")
            pathlib.Path(src).write_text("new")
            run("CopyFile", src=src, dst=dst, overwrite=0)          # must not overwrite
            self.assertEqual(pathlib.Path(dst).read_text(), "hello")
            run("CopyFile", src=src, dst=dst, overwrite=1)
            self.assertEqual(pathlib.Path(dst).read_text(), "new")
            run("CopyFile", src=src, dst=d + os.sep + "sub_target")   # not a dir -> plain file copy
            run("DeleteFile", path=dst)
            self.assertFalse(os.path.exists(dst))
            run("DeleteFile", path=dst)                              # already gone: no error

    def test_download_from_file_url(self):
        with tempfile.TemporaryDirectory() as d:
            src = pathlib.Path(d, "s.bin")
            src.write_bytes(b"x" * 200000)
            out = pathlib.Path(d, "out")
            out.mkdir()
            run("Download", url=src.as_uri(), dest=str(out))
            self.assertEqual((out / "s.bin").read_bytes(), src.read_bytes())
            self.assertFalse((out / "s.bin.part").exists())

    def test_wait_color(self):
        with mock.patch.object(winapi, "get_pixel", return_value=(250, 5, 5)):
            self.assertTrue(run("WaitColor", x=1, y=1, color="FF0000", tolerance=10, timeout=1))
        with mock.patch.object(winapi, "get_pixel", return_value=(0, 0, 255)):
            self.assertFalse(run("WaitColor", x=1, y=1, color="FF0000", tolerance=10, timeout=0.1))
            self.assertTrue(run("WaitColor", x=1, y=1, color="FF0000", timeout=0.1, on_timeout="continue"))
            self.assertTrue(run("WaitColor", x=1, y=1, color="FF0000", until="absent", timeout=1))

    def test_parse_color(self):
        self.assertEqual(actions.parse_color("#0a0B0c"), (10, 11, 12))
        self.assertEqual(actions.parse_color("0xFF0000"), (255, 0, 0))
        with self.assertRaises(ValueError):
            actions.parse_color("red")

    def test_real_pixel_and_screen(self):
        p = winapi.get_pixel(0, 0)
        self.assertTrue(p is None or len(p) == 3)
        self.assertGreater(winapi.virtual_screen()[2], 0)

    def test_windows_lookup(self):
        wins = winapi.list_windows()
        self.assertTrue(wins)
        hwnd, title = wins[0]
        self.assertEqual(winapi.find_window(title), hwnd if winapi.find_window(title) == hwnd else winapi.find_window(title))
        self.assertIsNone(winapi.find_window("zzz-no-such-window-zzz"))
        with self.assertRaises(RuntimeError):
            run("WinActivate", title="zzz-no-such-window-zzz")
        self.assertTrue(run("WinClose", title="zzz-no-such-window-zzz"))   # nothing to close: fine
        self.assertTrue(run("WinWaitClose", title="zzz-no-such-window-zzz", timeout=1))
        self.assertFalse(run("WinWait", title="zzz-no-such-window-zzz", timeout=0.1))

    def test_control_on_real_window(self):
        """Drive a genuine native checkbox (created via ctypes) through every Control* action."""
        import ctypes
        from ctypes import wintypes
        u = winapi.user32
        u.CreateWindowExW.restype = wintypes.HWND
        u.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                      ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                      wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
        u.IsWindowEnabled.argtypes = [wintypes.HWND]
        u.IsWindowVisible.argtypes = [wintypes.HWND]
        u.DestroyWindow.argtypes = [wintypes.HWND]
        WS_VISIBLE, WS_CHILD, BS_AUTOCHECKBOX = 0x10000000, 0x40000000, 3
        top = u.CreateWindowExW(0, "STATIC", "OpenReMouse-test-window", WS_VISIBLE | 0x00C00000,
                                50, 50, 300, 200, None, None, None, None)
        box = u.CreateWindowExW(0, "BUTTON", "Go-checkbox", WS_VISIBLE | WS_CHILD | BS_AUTOCHECKBOX,
                                10, 10, 200, 30, top, None, None, None)
        self.assertTrue(top and box)
        try:
            w = dict(window="OpenReMouse-test-window", control="Go-checkbox")
            self.assertEqual(winapi.find_control(top, "class:Button"), box)
            run("ControlClick", **w)
            self.assertEqual(u.SendMessageW(box, 0xF0, 0, 0), 1)         # BM_GETCHECK -> checked
            run("ControlDisable", **w)
            self.assertFalse(u.IsWindowEnabled(box))
            run("ControlEnable", **w)
            self.assertTrue(u.IsWindowEnabled(box))
            run("ControlHide", **w)
            self.assertFalse(u.IsWindowVisible(box))
            run("ControlShow", **w)
            self.assertTrue(u.IsWindowVisible(box))
            run("ControlFocus", **w)
            run("WinFlash", title="OpenReMouse-test-window", count=1)
            run("WinActivate", title="OpenReMouse-test-window")
            self.assertTrue(run("WinWait", title="OpenReMouse-test-window", timeout=1))
            with self.assertRaises(RuntimeError):
                run("ControlClick", window="OpenReMouse-test-window", control="nope-nope")
        finally:
            u.DestroyWindow(top)

    def test_process_helpers(self):
        self.assertTrue(actions.process_running("explorer"))
        self.assertFalse(actions.process_running("definitely-not-running-xyz"))

    def test_player_runs_cmd_and_reports_errors(self):
        p = Player()
        p.play(rms.loads("{Delay 0.01}\n{WaitColor x=0 y=0 color=000000 tolerance=255 timeout=1}"))
        self.assertIsNone(p.error)
        p = Player()
        p.play(rms.loads("{WinActivate title=zzz-no-such-window-zzz}\n{MessageBox text=never}"))
        self.assertIn("introuvable", p.error)
        p = Player()
        p.play(rms.loads("{NoSuchAction a=1}"))
        self.assertIn("inconnue", p.error)

    def test_player_stop_interrupts_wait(self):
        p = Player()
        threading.Timer(0.3, p.stop).start()
        t0 = time.monotonic()
        p.play(rms.loads("{WaitColor x=0 y=0 color=010203 tolerance=0 timeout=0}"))
        self.assertLess(time.monotonic() - t0, 3)

    def test_live_mouse_move_and_back(self):
        from pynput import mouse
        c = mouse.Controller()
        x, y = c.position
        p = Player()
        p.play(rms.loads("{Movements (0.00:%d:%d|0.01:%d:%d)}" % (x + 7, y, x, y)))
        self.assertEqual(tuple(c.position), (x, y))


if __name__ == "__main__":
    unittest.main()
