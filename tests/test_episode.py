"""Steps 5b/5c: the voice sets each shot's slot, and the 3D camera and the
kits are timed to it."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import episode  # noqa: E402
import narration  # noqa: E402
import sheet_writer as SW  # noqa: E402
from kits import timemap  # noqa: E402
from kits.blueprint import FPS  # noqa: E402

SHEET = os.path.join(os.path.dirname(__file__), "..", "src", "kits", "sheets", "i35w.json")


def sheet():
    s = json.load(open(SHEET))
    s["shots"] = [{"clip": c, "caption": "", "narration": "x"} for _, _, c, _ in SW.SHOTS]
    return s


class EpisodeTimingTest(unittest.TestCase):
    def test_slot_is_breath_voice_pause(self):
        voiced = {"physics": {"seconds": 60.0}, "clock": {"seconds": 0.5}}
        slots = narration.slots_of(sheet(), voiced)
        self.assertAlmostEqual(slots["physics"], narration.PAD_IN + 60 + narration.PAD_OUT)
        self.assertEqual(slots["clock"], narration.MIN_SLOT)

    def test_3d_shots_last_as_long_as_their_slots(self):
        slots = {c: 10.0 + i for i, (_, _, c, _) in enumerate(SW.SHOTS)}
        s = episode.timing(sheet(), slots, ai=True)
        tm, d = timemap.of(s), s["timing"]["dissolve"]
        self.assertAlmostEqual(tm.real(7.0), slots["establish"] + d)
        self.assertAlmostEqual(tm.real(20.0) - tm.real(7.0),
                               slots["load_path"] + slots["connection"] + d)
        # the fall shot ends on the AI clip's first frame
        fall = timemap.ai_start_frame(s) / FPS - tm.real(20.0)
        self.assertAlmostEqual(fall, slots["fall"] + episode.AI_BLEND, delta=1.5 / FPS)
        self.assertEqual(s["timing"]["kit"]["physics"], slots["physics"] + d)

    def test_3d_fall_drops_as_the_dramatization_begins(self):
        slots = {c: 10.0 + i for i, (_, _, c, _) in enumerate(SW.SHOTS)}
        tm = timemap.of(episode.timing(sheet(), slots))
        self.assertAlmostEqual(tm.real(22.0) - tm.real(20.0), slots["fall"])
        self.assertAlmostEqual(tm.real(28.0) - tm.real(22.0), 9.0)

    def test_photos_go_where_their_titles_say(self):
        cands = [{"title": "I-35W bridge"}, {"title": "Collapsed span wreckage", "year": 2007},
                 {"title": "NTSB gusset plate U10", "year": 2008},
                 {"title": "Bridge before", "year": 1990},
                 {"title": "Saint Anthony Falls Bridge", "year": 2012}]
        shots = episode.assign(sheet(), cands)
        self.assertEqual(shots["photo"][0]["title"], "I-35W bridge")
        self.assertEqual([c["title"] for c in shots["aftermath"]], ["Collapsed span wreckage"])
        self.assertEqual([c["title"] for c in shots["investigation"]], ["NTSB gusset plate U10"])
        self.assertEqual([c["title"] for c in shots["today_photos"]], ["Saint Anthony Falls Bridge"])
        self.assertEqual([c["title"] for c in shots["photos_disaster"]], ["Bridge before"])

    def test_timeline_lands_on_spoken_dates_and_slots_the_rest(self):
        s = sheet()
        s["timeline"] = [{"date": d} for d in ("1977", "1990", "1998", "2001", "JUNE 2003", "JANUARY 2007")]
        text = "Warnings came. In 1990 it was rated deficient. In 2001 a study. In June 2003 photos. In January 2007 cancelled."
        words = [{"word": w, "start": i * 0.5} for i, w in enumerate(text.split())]
        got = [round(t - narration.PAD_IN, 2) for t in episode.timeline_reveal(s, words)]
        said = {w["word"].strip(".,"): w["start"] for w in words}
        self.assertEqual(got[1], said["1990"])
        self.assertEqual(got[3], said["2001"])
        self.assertEqual(got[4], said["June"])
        self.assertEqual(got[5], said["January"])
        self.assertTrue(got[0] < got[1] and got[1] < got[2] < got[3])   # unsaid ones slot in, in order

    def test_photo_of_another_city_is_dropped(self):
        hyatt = {"disaster": {"place": "Hyatt Regency Kansas City atrium",
                              "place_date": "KANSAS CITY · 17 JULY 1981", "photo_article": "Hyatt Regency walkway collapse"}}
        self.assertTrue(episode.other_city({"title": "Hyatt Regency Embarcadero Atrium, San Francisco, US"}, hyatt))
        self.assertFalse(episode.other_city({"title": "Figure 5.6 - NARA - 70172359"}, hyatt))
        self.assertFalse(episode.other_city({"title": "Hyatt Regency Kansas City skywalk"}, hyatt))

    def test_credit_is_short(self):
        self.assertEqual(episode._short_credit(
            "I-35W collapse — Kevin Rofidal, USCG — Public domain (via Wikimedia Commons)"),
            "Photo: Kevin Rofidal, USCG · Public domain")

    def test_clock_times_are_said_like_a_narrator(self):
        self.assertEqual(narration.spoken("August 1, 2007. 6:05 p.m. Rush hour."),
                         "August 1, 2007. five past six in the evening. Rush hour.")
        self.assertEqual(narration.spoken("at 7:05 p.m., the walkways fell"),
                         "at five past seven in the evening, the walkways fell")
        self.assertEqual(narration.spoken("opened at 5 a.m. on September 18"),
                         "opened at five in the morning on September 18")
        self.assertEqual(narration.spoken("by 18:30"), "by half past six in the evening")
        self.assertEqual(narration.spoken("In 1990, 13 people, a 2:1 ratio"), "In 1990, 13 people, a 2:1 ratio")


if __name__ == "__main__":
    unittest.main()
