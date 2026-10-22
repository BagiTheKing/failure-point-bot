import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))

from story_short import _ramp, _word_at   # noqa: E402

WORDS = [("That", 10.0, 10.2), ("doubled", 10.3, 10.7), ("the", 10.8, 10.9), ("load.", 11.0, 11.4)]


def test_word_found_after_a_second():
    assert _word_at(WORDS, "doubled") == (10.3, 10.7)
    assert _word_at(WORDS, "Load") == (11.0, 11.4)               # case and punctuation ignored
    assert _word_at(WORDS, "doubled", after=10.5) is None


def test_ramp_runs_zero_to_one():
    assert _ramp(0.9, 1.0, 0.5) == 0.0
    assert _ramp(1.25, 1.0, 0.5) == 0.5
    assert _ramp(2.0, 1.0, 0.5) == 1.0
