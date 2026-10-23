import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from episode import VICTIMS  # noqa: E402


def test_the_victims_last_moments_are_never_used():
    assert VICTIMS.search("STS-107, final moments in cabin (Space Shuttle Columbia disaster)")


def test_mission_control_and_briefings_are_fine():
    assert not VICTIMS.search("Shuttle Columbia Disaster - Flight Director Communications Loop")
    assert not VICTIMS.search("STS 107 Columbia 2003 02 14 Entry Flight Director Briefing NASA")
    assert not VICTIMS.search("I-35W bridge collapse surveillance camera")
