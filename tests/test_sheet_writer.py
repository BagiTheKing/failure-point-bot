"""Step 5a: the writer's animation sheet is checked before any kit uses it."""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import sheet_writer as SW  # noqa: E402

SOURCE = ("The Hyatt Regency walkways fell on 17 July 1981 at 7:05 pm in Kansas City. "
          "114 people were killed and 216 injured; about 1,600 people were in the atrium. "
          "In 1979 the rod design was changed. In October 1979 part of the atrium roof "
          "collapsed. The hotel opened on 1 July 1980. Load doubled: 2 walkways on one nut.")


def reply():
    words = lambda n: " ".join(["word"] * n)
    return {
        "kit": {"variant": "hanging_walkways", "levels": ["4th-floor walkway", "2nd-floor walkway"],
                "rod_lines": 3, "failed_line": 1,
                "labels": {"roof": "roof trusses", "rods": "steel hanger rods", "beam": "box beam",
                           "nut": "one nut holds everything", "upper_rod": "UPPER ROD",
                           "lower_rod": "LOWER ROD"}},
        "labels_3d": {"upper_deck": "4th-floor walkway", "nut": "the nut"},
        "big_3d": {"text": "2×", "label": "LOAD ON ONE NUT"},
        "disaster": {"place_date": "KANSAS CITY · 17 JULY 1981 · 7:05 PM", "place": "Hyatt Regency",
                     "caption": "Two walkways fell."},
        "design_vs_built": {"designed": {"title": "AS DESIGNED", "detail": "one rod", "load": "1 walkway"},
                            "built": {"title": "AS BUILT", "detail": "two rods", "load": "2 walkways"},
                            "multiplier": "2×", "multiplier_label": "LOAD ON ONE NUT"},
        "numbers": [{"value": "114", "label": "PEOPLE KILLED"}, {"value": "216", "label": "INJURED"}],
        "clock": {"at": "7:05", "day": "PM · FRIDAY 17 JULY 1981", "event": "THE CONNECTION FAILS"},
        "timeline": [{"date": "1979", "title": "Rod design changed", "sub": "", "kind": "warning"},
                     {"date": "OCT 1979", "title": "Roof collapses", "sub": "", "kind": "warning"},
                     {"date": "17 JUL 1981", "title": "Walkways fall", "sub": "", "kind": "failure"}],
        "today": {"title": "COULD IT HAPPEN TODAY?", "lines": ["a", "b", "c"]},
        "ai_prompt": "The upper walkway drops flat. Static camera.",
        "photo_article": "Hyatt Regency walkway collapse",
        "shots": {clip: {"caption": "A short line.", "narration": words(w)}
                  for _, _, clip, w in SW.SHOTS},
    }


class SheetWriterTest(unittest.TestCase):
    def test_good_reply_passes_and_assembles(self):
        self.assertEqual(SW.check(reply(), "hanging_walkways", SOURCE), [])
        sheet = SW.assemble(reply(), "hanging_walkways", "https://example")
        self.assertEqual(sheet["kit"]["variant"], "hanging_walkways")
        self.assertEqual([s["clip"] for s in sheet["shots"]], [c for _, _, c, _ in SW.SHOTS])
        from kits.timemap import ai_start_frame
        self.assertEqual(ai_start_frame(sheet), 655)
        self.assertEqual(sheet["model_3d"]["big_3d"]["anchor"], "nut")
        # only the 3D slots the writer filled get a label
        self.assertEqual({l["anchor"] for l in sheet["model_3d"]["labels_3d"]}, {"upper_deck"})

    def test_clock_counts_down_to_the_moment(self):
        c = SW.assemble(reply(), "hanging_walkways")["clock"]
        self.assertEqual(c["label_before"].format(s=55), "7:04:55")
        self.assertEqual(c["label_at"], "7:05:00")
        self.assertEqual(SW.clock_of({"at": "6:00"})["label_before"].format(s=50), "5:59:50")

    def test_invented_figure_is_refused(self):
        r = reply()
        r["numbers"][0]["value"] = "140"
        self.assertTrue(any("140" in p for p in SW.check(r, "hanging_walkways", SOURCE)))

    def test_thin_narration_is_refused(self):
        r = reply()
        r["shots"]["physics"]["narration"] = "Too short."
        self.assertTrue(any("physics" in p for p in SW.check(r, "hanging_walkways", SOURCE)))

    def test_placeholder_left_is_refused(self):
        r = reply()
        r["disaster"]["place"] = "<where, one line>"
        self.assertTrue(any("placeholder" in p for p in SW.check(r, "hanging_walkways", SOURCE)))

    def test_kit_parameters_are_checked(self):
        r = reply()
        r["kit"]["failed_line"] = 5
        self.assertTrue(any("failed_line" in p for p in SW.check(r, "hanging_walkways", SOURCE)))
        t = copy.deepcopy(reply())
        t["kit"] = {"variant": "truss_bridge", "deck": "top", "spans": [266, 456, 266],
                    "panels": 28, "failed_node": 40, "failed_node_label": "U10",
                    "load_near_node": True, "labels": {}}
        self.assertTrue(any("failed_node" in p for p in SW.check(t, "truss_bridge", SOURCE + " 266 456 28 10")))


if __name__ == "__main__":
    unittest.main()
