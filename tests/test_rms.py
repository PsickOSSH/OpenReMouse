import pathlib
import unittest

from openremouse import rms

EX = pathlib.Path(__file__).parent.parent / "examples"


class RmsTests(unittest.TestCase):
    def test_roundtrip_examples(self):
        for f in EX.glob("*.rms"):
            acts = rms.load(str(f))
            self.assertTrue(acts, f.name)
            self.assertFalse([a for a in acts if a.kind == "raw"], f.name)
            self.assertEqual(rms.dumps(rms.loads(rms.dumps(acts))), rms.dumps(acts))

    def test_values(self):
        a = rms.loads("{Delay 0.50}\n{RMouse down (225,202)}\n{Movements (0.36:226:192|0.05:254:192)}\n{Key down a}")
        self.assertEqual(a[0].delay, 0.5)
        self.assertEqual((a[1].button, a[1].pressed, a[1].x, a[1].y), ("RMouse", True, 225, 202))
        self.assertEqual(a[2].moves, [(0.36, 226, 192), (0.05, 254, 192)])
        self.assertEqual((a[3].key, a[3].pressed), ("a", True))

    def test_unknown_line_kept(self):
        a = rms.loads("{Something new 1 2 3}")
        self.assertEqual(a[0].kind, "raw")
        self.assertEqual(a[0].to_line(), "{Something new 1 2 3}")

    def test_cmd_roundtrip_with_awkward_values(self):
        args = {"text": 'say "hi"\nline2\tTab \\ back', "empty": "", "path": r"C:\Program Files\x.exe",
                "plain": "FF0000"}
        a = rms.Action("cmd", name="TypeText", args=args)
        line = a.to_line()
        self.assertNotIn("\n", line)
        b = rms.parse_line(line)
        self.assertEqual((b.kind, b.name, b.args), ("cmd", "TypeText", args))

    def test_cmd_without_args(self):
        a = rms.parse_line("{CheckInternet}")
        self.assertEqual((a.kind, a.name, a.args), ("cmd", "CheckInternet", {}))

    def test_exotic_line_separator_in_value_does_not_split_lines(self):
        a = rms.Action("cmd", name="TypeText", args={"text": "a\u2028b\x0cc"})
        out = rms.loads(rms.dumps([a, rms.Action("delay", delay=1)]))
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].args["text"], "a\u2028b\x0cc")


if __name__ == "__main__":
    unittest.main()
