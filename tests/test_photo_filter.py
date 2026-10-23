import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from episode import _excluded  # noqa: E402


def test_remains_and_coffins_are_never_used():
    c = {"title": "A US Air Force Honor Guard removes a coffin carrying the remains of a crewmember"}
    assert _excluded(c, {})


def test_the_sheet_can_rule_out_more():
    assert _excluded({"title": "Columbia Memorial"}, {"photo_exclude": "memorial"})
    assert not _excluded({"title": "Columbia Memorial"}, {})


def test_debris_and_investigators_are_fine():
    assert not _excluded({"title": "Grid with Columbia's Debris - GPN-2003-00081"}, {})
    assert not _excluded({"title": "Chairman Gehman - GPN-2003-00084"}, {})


def test_a_pin_needs_the_names_it_searched_for():
    from episode import _names_match
    assert not _names_match("Teton Dam remains", {"title": "-81 RC Gym burn (7004236633)", "about": ""})
    assert _names_match("TetonDamRemains01", {"title": "TetonDamRemains01", "about": ""})
    assert _names_match("STS-114 launch Discovery",
                        {"title": "STS-114 launch", "about": "Space Shuttle Discovery lifts off"})
