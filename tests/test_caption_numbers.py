import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from highlight_short import chunks  # noqa: E402


def _groups(text):
    words = [(w, i, i + 0.3) for i, w in enumerate(text.split())]
    return [" ".join(w for w, _, _ in g) for g in chunks(words)]


def test_a_spoken_decimal_shows_as_digits_never_a_stray_digit():
    g = _groups("built for an impact of zero point zero zero six foot-pounds. But foam")
    assert "0.006 foot-pounds." in g
    assert not any(x.lower().startswith("six") for x in g)


def test_a_spoken_number_stays_with_what_it_counts():
    g = _groups("Investigators recovered eighty-four thousand pieces of Columbia.")
    assert g == ["Investigators recovered", "eighty-four thousand pieces", "of Columbia."]


def test_plain_words_still_group_by_three():
    assert _groups("Space Shuttle Columbia breaks apart over Texas,") == [
        "Space Shuttle Columbia", "breaks apart over", "Texas,"]
