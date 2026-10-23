import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sheet_writer import clock_of  # noqa: E402


def labels(at):
    c = clock_of({"at": at})
    out = []
    for secs in range(11):
        s = c["from_seconds"] + secs
        out.append(c["label_at"] if secs >= 10 else c["label_next"].format(s=s - 60) if s >= 60
                   else c["label_before"].format(s=s))
    return out


def test_a_moment_on_the_minute_counts_the_last_ten_seconds():
    assert labels("7:05")[0] == "7:04:50" and labels("7:05")[-1] == "7:05:00"


def test_a_moment_to_the_second_counts_to_that_second():
    assert labels("9:00:18")[0] == "9:00:08" and labels("9:00:18")[-1] == "9:00:18"


def test_the_count_crosses_the_minute_cleanly():
    assert labels("9:01:03") == ["9:00:53", "9:00:54", "9:00:55", "9:00:56", "9:00:57", "9:00:58",
                                 "9:00:59", "9:01:00", "9:01:01", "9:01:02", "9:01:03"]
