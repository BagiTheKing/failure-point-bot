"""The 48-hour channel spacing (src/upload_gate.py; owner, 2026-10-17)."""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import upload_gate  # noqa: E402

NOW = datetime.datetime(2026, 10, 20, 12, 0, tzinfo=datetime.timezone.utc)


def at(hours_ago):
    return (NOW - datetime.timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


class UploadGateTest(unittest.TestCase):
    def test_empty_channel_goes(self):
        self.assertTrue(upload_gate.decide([], now=NOW)[0])

    def test_post_inside_48h_stands_down(self):
        go, reason = upload_gate.decide([{"title": "Hyatt", "publishedAt": at(30)}], now=NOW)
        self.assertFalse(go)
        self.assertIn("next slot", reason)

    def test_post_older_than_48h_goes(self):
        self.assertTrue(upload_gate.decide([{"title": "Hyatt", "publishedAt": at(49)}], now=NOW)[0])

    def test_any_format_counts(self):
        # a Short posted by hand 10 h ago holds a long video too
        videos = [{"title": "long", "publishedAt": at(100), "duration": "PT14M"},
                  {"title": "short by hand", "publishedAt": at(10), "duration": "PT50S"}]
        self.assertFalse(upload_gate.decide(videos, now=NOW)[0])

    def test_scheduled_publish_counts_at_its_publish_time(self):
        # uploaded 60 h ago, but scheduled to go public 12 h from now:
        # the next post waits until 60 h from now
        videos = [{"title": "highlight", "publishedAt": at(60), "publishAt": at(-12)}]
        go, _ = upload_gate.decide(videos, now=NOW)
        self.assertFalse(go)
        slot = upload_gate.next_free_slot(videos)
        self.assertEqual(slot, NOW + datetime.timedelta(hours=60))

    def test_spacing_can_be_disabled(self):
        self.assertTrue(upload_gate.decide([{"publishedAt": at(1)}], now=NOW, hours=0)[0])


if __name__ == "__main__":
    unittest.main()
