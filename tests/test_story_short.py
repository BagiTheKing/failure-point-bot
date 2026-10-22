import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))

from kits.blueprint import Beats          # noqa: E402
from story_short import _kit_time, _word_at   # noqa: E402

WORDS = [("That", 10.0, 10.2), ("doubled", 10.3, 10.7), ("the", 10.8, 10.9), ("load.", 11.0, 11.4)]


def test_word_found_after_a_second():
    assert _word_at(WORDS, "doubled") == (10.3, 10.7)
    assert _word_at(WORDS, "doubled", after=10.5) is None


def test_kit_time_pins_a_beat_to_its_word():
    b = Beats(("show", 1.0, 0.6), ("loads", 0.8, 2.6), ("mark", 0.6, 2.4))
    kt = _kit_time(b, {"from": "show", "to": "mark", "cue": {"doubled": "loads"}}, 10.0, 12.0, WORDS)
    assert kt(10.0) == b.start("show")
    assert abs(kt(10.3) - b.start("loads")) < 1e-6          # lands on the word
    assert abs(kt(12.0) - (b.end("mark") + 0.4)) < 1e-6
    assert all(kt(10 + i / 10) <= kt(10 + (i + 1) / 10) for i in range(20))   # never runs back
