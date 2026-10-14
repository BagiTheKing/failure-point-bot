"""
Failure Point's own pieces: the engineering topic pool, the news lane and its
anniversary fallback. Offline, no keys.

    python -m unittest discover tests
"""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import failure_news
import formats
import longform_llm as L
import longform_main as M
import topics


class TopicPool(unittest.TestCase):

    def test_every_topic_has_a_known_format_and_reach(self):
        for t in topics.CORE_TOPICS:
            self.assertIn(topics.format_of(t), formats.FORMATS, t)
            self.assertIn(topics.reach_of(t), topics.REACH_ORDER, t)

    def test_no_duplicates(self):
        self.assertEqual(len(topics.CORE_TOPICS), len(set(topics.CORE_TOPICS)))

    def test_every_pool_topic_reads_as_a_story(self):
        # find_story drops a topic that does not read as an event and spends
        # an LLM call turning it into one; the pool must never need that.
        for t in topics.CORE_TOPICS:
            self.assertTrue(L._anchor_fits_niche(t, story=True), t)

    def test_anniversary_dates_are_real_dates(self):
        for t, mmdd in topics.ANNIVERSARY.items():
            month, day = (int(x) for x in mmdd.split("-"))
            datetime.date(2024, month, day)     # raises on a bad date

    def test_free_text_topics_get_the_right_format(self):
        cases = {
            "A crane collapse at a Seattle construction site": "collapse",
            "The 1928 St. Francis Dam failure": "breach",
            "A refinery explosion in Texas": "blast",
            "A ferry capsized off the coast": "sinking",
            "A train derailment in Ohio": "machine",
        }
        for text, want in cases.items():
            self.assertEqual(topics.format_of(text), want, text)

    def test_pick_topic_skips_published(self):
        first = topics.pick_topic()
        self.assertIsNotNone(first)
        self.assertNotEqual(topics.pick_topic(exclude=[first]), first)


class Anniversaries(unittest.TestCase):

    def test_closest_first(self):
        # Hyatt Regency is 17 July; Port Chicago is 17 July too, West Gate
        # is 15 October.
        got = topics.anniversary_topics(datetime.date(2026, 7, 16), window=1)
        self.assertTrue(got)
        self.assertTrue(all(topics.ANNIVERSARY[t] in ("07-15", "07-16", "07-17")
                            for t in got))

    def test_wraps_the_year_end(self):
        got = topics.anniversary_topics(datetime.date(2027, 1, 1), window=3)
        self.assertTrue(any(topics.ANNIVERSARY[t] == "12-29" for t in got))

    def test_excluded_topics_stay_out(self):
        day = datetime.date(2026, 7, 17)
        got = topics.anniversary_topics(day, window=0)
        self.assertTrue(got)
        self.assertNotIn(got[0], topics.anniversary_topics(day, 0, exclude=[got[0]]))


class FailureNews(unittest.TestCase):

    def setUp(self):
        self.real_get = failure_news._get

    def tearDown(self):
        failure_news._get = self.real_get

    @staticmethod
    def _feed(*titles):
        items = "".join(f"<item><title>{t} - Some Paper</title></item>" for t in titles)
        return f"<rss><channel>{items}</channel></rss>".encode()

    def test_ranks_widely_reported_stories_and_drops_war_and_weather(self):
        feeds = {
            "bridge": self._feed("Highway bridge collapses into river in Brazil",
                                 "Missile strike collapses bridge in war zone"),
            "plant": self._feed("Chemical plant explosion injures 12 in Ohio",
                                "Earthquake causes building collapse"),
        }

        def fake_get(url):
            return feeds["bridge" if "bridge" in url else "plant"]

        failure_news._get = fake_get
        got = failure_news.get_failure_news(
            queries=["bridge collapse", "plant explosion", "bridge collapse again"])
        subjects = [c["subject"] for c in got]
        self.assertEqual(subjects[0], "Highway bridge collapses into river in Brazil")
        self.assertIn("Chemical plant explosion injures 12 in Ohio", subjects)
        self.assertFalse(any("Missile" in s or "Earthquake" in s for s in subjects))

    def test_dead_feed_gives_nothing_not_an_error(self):
        def boom(url):
            raise OSError("403 Forbidden")
        failure_news._get = boom
        self.assertEqual(failure_news.get_failure_news(queries=["dam failure"]), [])


class EngineeringAnchor(unittest.TestCase):

    def setUp(self):
        self.real_call = L._call

    def tearDown(self):
        L._call = self.real_call

    def test_too_recent_is_re_asked_then_accepted(self):
        replies = iter([
            {"subject": "Crane collapse in Seattle", "topic":
             "The 2019 Seattle crane collapse, where pins were removed early",
             "anchor_year": 2019, "why": "same kind of failure"},
            {"subject": "Crane collapse in Seattle", "topic":
             "The 1989 San Francisco crane collapse, where a tower crane "
             "failed during a lift", "name": "San Francisco crane collapse",
             "anchor_year": 1989, "why": "same kind of failure"},
        ])
        asked = []

        def fake_call(pool, system, user, max_tokens, **kw):
            asked.append(user)
            return next(replies)

        L._call = fake_call
        got = L.select_engineering_anchor([{"subject": "Crane collapses in Seattle"}],
                                          pool=object())
        self.assertEqual(got["anchor_year"], 1989)
        self.assertEqual(len(asked), 2)
        self.assertIn("2019", asked[1])

    def test_not_an_engineering_failure_is_rejected(self):
        L._call = lambda *a, **k: {"subject": "x", "topic":
                                   "The 1815 Congress of Vienna redraws Europe",
                                   "anchor_year": 1815, "why": "politics"}
        self.assertIsNone(L.select_engineering_anchor(
            [{"subject": "Bridge collapses"}], pool=object()))


class TimelyLane(unittest.TestCase):
    """A quiet news week must still give the lane a topic: this week's
    anniversary, then the rotation."""

    def setUp(self):
        self.real_news = failure_news.get_failure_news

    def tearDown(self):
        failure_news.get_failure_news = self.real_news

    def test_quiet_week_takes_an_anniversary(self):
        failure_news.get_failure_news = lambda *a, **k: []
        os.environ["ANNIVERSARY_WINDOW_DAYS"] = "200"
        try:
            topic, enforce, from_short, _ = M.resolve_topic("timely", history=None)
        finally:
            del os.environ["ANNIVERSARY_WINDOW_DAYS"]
        self.assertIn(topic, topics.ANNIVERSARY)
        self.assertFalse(enforce)
        self.assertFalse(from_short)
        self.assertIsNone(M.LAST_TREND["subject"])


if __name__ == "__main__":
    unittest.main()
