"""
Real archive pictures in the Shorts, beside the generated paintings.

Every frame of a Short used to be an AI oil painting. On a channel whose whole
claim is "this really happened", one real photograph of the ship, the man or
the battlefield is the proof a painting cannot be, and the long-form lanes
have had the search for it (archive_engine.py) all along.

Up to SHORTS_ARCHIVE_FRAMES pictures a video, from two places, in this order:
  1. the writer's archive_query for a scene, searched on Wikimedia Commons
     and the Library of Congress. A result is used only if its file title
     carries the query's words (archive_engine.footage_matches): an
     unrelated real photo reads worse than a good painting;
  2. the lead image of the story's Wikipedia article (shorts_facts), for the
     earliest scene still without one.

A picture does not replace the scene's painting: it becomes one of the scene's
shots (video_engine.plan_shots), so the generator's daily allowance is spent
exactly as before. Every picture is credited in the description.
"""

import os

import math
import re

from archive_engine import (article_images, article_lead_image,
                            download_archival_image, fit_vertical,
                            footage_matches, format_credit, search_archives)

ARCHIVE_FRAMES = int(os.getenv("SHORTS_ARCHIVE_FRAMES", "6"))
PER_SCENE = int(os.getenv("SHORTS_ARCHIVE_PER_SCENE", "2"))
W, H = 1080, 1920
CANDIDATES_PER_QUERY = 6


def _fetch(candidate, scene, idx, build_dir):
    k = len(scene.get("archive_paths") or [])
    path = os.path.join(build_dir, f"archive_{idx}{'_' + str(k) if k else ''}.jpg")
    if not download_archival_image(candidate, path, W, H, fit=fit_vertical):
        return False
    credit = format_credit(candidate)
    scene.setdefault("archive_paths", []).append(path)
    scene.setdefault("archive_credits", []).append(credit)
    scene.setdefault("archive_path", path)
    scene.setdefault("archive_credit", credit)
    print(f"🗄️  Scene {idx}: archive frame — {credit[:90]}")
    return True


def add_archive_frames(script_data: dict, build_dir: str = "build") -> int:
    """Attaches archive_path/archive_credit to up to ARCHIVE_FRAMES scenes.
    Returns how many were found. Never raises: a Short without a real
    picture is still a Short."""
    if ARCHIVE_FRAMES <= 0:
        return 0
    scenes = [(i, s) for i, s in enumerate(script_data.get("scenes") or [])
              if not s.get("is_outro")]
    used, found = set(), 0
    try:
        for idx, scene in scenes:
            if found >= ARCHIVE_FRAMES:
                break
            query = (scene.get("archive_query") or "").strip()
            if not query:
                continue
            for cand in search_archives(query, limit=12)[:CANDIDATES_PER_QUERY * PER_SCENE]:
                if cand["url"] in used:
                    continue
                if not footage_matches(query, (cand.get("title") or "").lower()):
                    continue
                if _fetch(cand, scene, idx, build_dir):
                    used.add(cand["url"])
                    found += 1
                    if (len(scene["archive_paths"]) >= PER_SCENE
                            or found >= ARCHIVE_FRAMES):
                        break
            if not scene.get("archive_paths"):
                print(f"   🗄️  Scene {idx}: nothing on the archives matches "
                      f"{query!r}.")

        source_title = script_data.get("source_title")
        if found < ARCHIVE_FRAMES and source_title:
            lead = article_lead_image(source_title)
            # The hook is the painting's moment; the lead image goes to the
            # first scene after it that has no real picture yet.
            spare = [(i, s) for i, s in scenes[1:] if not s.get("archive_path")]
            if lead and lead["url"] not in used and spare:
                idx, scene = spare[0]
                if _fetch(lead, scene, idx, build_dir):
                    found += 1
    except Exception as e:
        print(f"⚠️ Archive frames skipped ({type(e).__name__}: {e}).")
    print(f"🗄️  {found} archive frame(s) in this Short.")
    return found


# ---------------------------------------------------------------------------
# Real pictures first (owner, 2026-10-17): "AI images should be used if and
# only if there is no real image for the scene, even if no AI image is used
# for the video". The first Failure Point Short was all AI with two real
# frames in its first scene. Every scene now takes real pictures before
# anything is generated: its own archive_query first, then the story's pool
# (the Wikipedia article's own pictures and a Commons search on the event's
# name). generate_visual_pipeline only draws the scenes left with nothing.
# ---------------------------------------------------------------------------

PICTURE_SECONDS = float(os.getenv("SHORTS_PICTURE_SECONDS", "3.5"))
# Words in an event's name that say what KIND of thing failed, not which one:
# a photo titled "garment factory" is not about the Triangle Shirtwaist
# Factory fire. Compared on their first five letters.
_GENERIC_STEMS = {w[:5] for w in (
    "factory", "fire", "bridge", "dam", "collapse", "disaster", "explosion",
    "flight", "mine", "mining", "colliery", "plant", "refinery", "tank",
    "flood", "sinking", "airship", "train", "railway", "reactor", "accident",
    "failure", "crash", "blast", "building", "tower", "roof", "walkway",
    "store", "theatre", "theater", "school", "station", "power", "platform",
    "submarine", "ship", "ferry", "levee", "reservoir", "crisis", "test",
    "explosions", "disaster", "center", "centre", "company")}
MAX_PER_SCENE = int(os.getenv("SHORTS_REAL_PER_SCENE", "3"))


def event_query(topic: str) -> str:
    """The event's name from a pool topic line: "The Triangle Shirtwaist
    Factory fire (1911), where ..." -> "Triangle Shirtwaist Factory fire"."""
    name = re.split(r"\s*\(|,|:\s| — ", topic or "", maxsplit=1)[0].strip()
    return re.sub(r"^the\s+", "", name, flags=re.I)


def story_pool(script_data: dict) -> list:
    """Real-picture candidates for the whole story, most relevant first,
    deduplicated: the article's lead image, the article's other pictures,
    then a Commons search on the event's name."""
    out, seen = [], set()

    def add(cands):
        for c in cands or []:
            if c and c.get("url") and c["url"] not in seen:
                seen.add(c["url"])
                out.append(c)

    title = script_data.get("source_title")
    if title:
        add([article_lead_image(title)])
        add(article_images(title))
    name = event_query(script_data.get("topic") or "")
    if name:
        add(search_archives(name, limit=15))
    return out


def fill_real_images(script_data: dict, build_dir: str = "build",
                     pool: list = None) -> int:
    """Gives every scene real pictures before any is generated. Sets
    image_path(s), archive_path(s) and image_source="archive" on each scene
    that got one. Returns how many real pictures were placed. Never raises."""
    scenes = [(i, s) for i, s in enumerate(script_data.get("scenes") or [])
              if not s.get("is_outro")]
    try:
        pool = list(story_pool(script_data) if pool is None else pool)
    except Exception as e:
        print(f"⚠️ Story picture pool unavailable ({type(e).__name__}: {e}).")
        pool = []
    print(f"🗄️  {len(pool)} real picture(s) found for this story.")
    used, placed = set(), 0
    seen_titles = set()
    # A scene's own search must still be about THIS story: on 2026-10-17
    # "garment factory interior" brought three Hong Kong museum photos into
    # the Triangle fire Short. The story's pool is already about it.
    event_stems = {w[:5] for w in re.findall(r"[a-z]+", event_query(
        script_data.get("topic") or "").lower())
        if len(w) >= 4 and w[:5] not in _GENERIC_STEMS}
    pool_urls = {c.get("url") for c in pool}

    def want(scene):
        return max(1, min(MAX_PER_SCENE,
                          math.ceil((scene.get("duration") or 0) / PICTURE_SECONDS)))

    def title_key(cand):
        # the same photo reached through two searches has two URLs (a
        # thumbnail and the original) but one title: the coffins photo ran
        # in two scenes of the second Short
        return re.sub(r"[^a-z0-9]", "", (cand.get("title") or "").lower())[:60]

    def take(scene, idx, cand):
        nonlocal placed
        key = title_key(cand)
        if cand["url"] in used or (key and key in seen_titles):
            return False
        if key:
            seen_titles.add(key)
        if _fetch(cand, scene, idx, build_dir):
            used.add(cand["url"])
            placed += 1
            return True
        used.add(cand["url"])        # a failed download is not retried
        return False

    try:
        # Pass 1: each scene's own subject, then one picture from the pool
        # for every scene still empty, so the pool is spread over the whole
        # video instead of spent on the first scenes.
        for idx, scene in scenes:
            query = (scene.get("archive_query") or "").strip()
            if query:
                for cand in search_archives(query, limit=12)[:CANDIDATES_PER_QUERY * 2]:
                    if len(scene.get("archive_paths") or []) >= want(scene):
                        break
                    title = (cand.get("title") or "").lower()
                    about_story = (cand.get("url") in pool_urls or not event_stems
                                   or any(st in title for st in event_stems))
                    if footage_matches(query, title) and about_story:
                        take(scene, idx, cand)
        for idx, scene in scenes:
            if scene.get("archive_paths"):
                continue
            for cand in pool:
                if cand["url"] not in used and take(scene, idx, cand):
                    break
        # Pass 2: what is left of the pool goes round the scenes that still
        # want more pictures, one at a time.
        more = True
        while more:
            more = False
            for idx, scene in scenes:
                if len(scene.get("archive_paths") or []) >= want(scene):
                    continue
                for cand in pool:
                    if cand["url"] not in used and take(scene, idx, cand):
                        more = True
                        break
    except Exception as e:
        print(f"⚠️ Real pictures stopped early ({type(e).__name__}: {e}).")

    empty = 0
    for idx, scene in scenes:
        paths = scene.get("archive_paths") or []
        if paths:
            scene["image_path"] = paths[0]
            scene["image_paths"] = list(paths)
            scene["image_source"] = "archive"
            scene["is_real"] = True
        else:
            empty += 1
    print(f"🗄️  {placed} real picture(s) placed; {empty} scene(s) left for "
          f"generation.")
    return placed


def archive_credits(script_data: dict) -> list:
    out = []
    for s in script_data.get("scenes") or []:
        for c in s.get("archive_credits") or ([s["archive_credit"]] if s.get("archive_credit") else []):
            if c not in out:
                out.append(c)
    return out
