import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import short_photo  # noqa: E402

ROAD_GUIDE = {"title": "Haynes new guide and motorists' complete road log of Yellowstone National Park (1922)",
              "about": ""}
BREACH = {"title": "Teton Dam failure", "about": "Teton Dam failing, 5 June 1976"}


def test_a_search_result_without_the_names_is_never_used(monkeypatch):
    monkeypatch.setattr(short_photo, "search_commons", lambda q, limit: [ROAD_GUIDE, BREACH])
    c, how = short_photo.pick({"photo_search": "Teton Dam failure"})
    assert c is BREACH and how == "search"


def test_the_named_file_comes_before_the_article_and_the_search(monkeypatch):
    monkeypatch.setattr(short_photo, "commons_file", lambda n: BREACH)
    monkeypatch.setattr(short_photo, "article_lead_image", lambda a: ROAD_GUIDE)
    c, how = short_photo.pick({"photo_file": "Teton Dam failure.jpg", "photo_article": "Teton Dam"})
    assert c is BREACH and how == "file"


def test_the_article_lead_image_comes_before_a_search(monkeypatch):
    monkeypatch.setattr(short_photo, "article_lead_image", lambda a: BREACH)
    monkeypatch.setattr(short_photo, "search_commons", lambda q, limit: [ROAD_GUIDE])
    c, how = short_photo.pick({"photo_article": "Teton Dam", "photo_search": "Teton Dam"})
    assert how == "article"


def test_nothing_fitting_is_none(monkeypatch):
    monkeypatch.setattr(short_photo, "search_commons", lambda q, limit: [ROAD_GUIDE])
    assert short_photo.pick({"photo_search": "Teton Dam failure"}) == (None, None)
