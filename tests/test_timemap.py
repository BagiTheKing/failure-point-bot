"""Step 5b: 3D shots stretch to their narration through one time map."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kits import timemap  # noqa: E402


class TimeMapTest(unittest.TestCase):
    def test_default_map_is_the_canonical_timeline(self):
        tm = timemap.TimeMap()
        self.assertAlmostEqual(tm.real(13.0), 13.0)
        self.assertEqual(tm.frame(21.8), 655)
        self.assertEqual(timemap.ai_start_frame({}), 655)

    def test_stretched_shots_move_everything_after_them(self):
        tm = timemap.TimeMap({"establish": 24, "load_path": 20, "connection": 18, "hold": 6})
        self.assertAlmostEqual(tm.real(7.0), 24.0)          # end of establish
        self.assertAlmostEqual(tm.real(3.5), 12.0)          # half-way through it
        self.assertAlmostEqual(tm.window("connection")[1], 62.0)
        self.assertAlmostEqual(tm.canon(tm.real(17.3)), 17.3)
        # the AI start stays inside the (longer) hold, after the pull-back
        start = tm.real(timemap.AI_START_CANON)
        self.assertTrue(tm.real(21.4) < start < tm.real(22.0))
        sheet = {"model_3d": {"shot_seconds": {"establish": 24}}}
        self.assertEqual(timemap.ai_start_frame(sheet), 655 + 17 * 30)


if __name__ == "__main__":
    unittest.main()
