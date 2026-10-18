"""
Publishes a finished episode to the channel: the video, the chosen
thumbnail, and a description built from the episode itself (hook, chapters,
sources, photo and footage credits, the music credits CC BY requires).

    python tools/publish_episode.py EPISODE_DIR --title "..." --thumb split [--publish-at 2026-10-19T18:00:00Z]

EPISODE_DIR holds episode.mp4, episode.json, timed_sheet.json and the
thumbnails (thumb_*.jpg). --dry-run writes description.txt and stops.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

CHANNEL = "The Point of Failure"


def description(sheet, info):
    hook = (sheet.get("hook") or {}).get("lines") or []
    lines = []
    if hook:
        lines += [" ".join(hook), ""]
    lines += ["How it failed, step by step: the structure, the forces, the part that gave way, "
              "the warnings that were missed, and what was changed after.", ""]
    if info.get("chapters"):
        lines += info["chapters"] + [""]
    src = [u for u in (sheet.get("sources") or {}).values() if u]
    lines += ["SOURCES"] + [f"• {u}" for u in src]
    if "ntsb" in json.dumps(sheet).lower():
        lines += ["• NTSB accident report on the collapse (National Transportation Safety Board)"]
    lines += ["", "The 3D and 2D animations are reconstructions made for this video from the "
              "investigation's findings; they show the mechanism, not footage of the event.", ""]
    if info.get("credits"):
        lines += ["PHOTOS AND FOOTAGE"] + [f"• {c}" for c in info["credits"]] + [""]
    if info.get("music_credits"):
        lines += ["MUSIC"] + [c.strip() for c in info["music_credits"]] + [""]
    lines += [f"{CHANNEL}: engineering disasters, explained."]
    text = "\n".join(lines)
    return text[:4900]                                   # YouTube's limit is 5,000 characters


def tags(sheet):
    place = sheet["disaster"].get("photo_article") or sheet["disaster"].get("place", "")
    base = [place, f"{place} collapse", "engineering disaster", "structural failure",
            "engineering explained", "disaster explained", "3D animation", "NTSB"]
    kit = sheet.get("kit", {}).get("variant", "")
    base += {"truss_bridge": ["bridge collapse", "gusset plate", "truss bridge"],
             "hanging_walkways": ["walkway collapse", "hanger rod", "structural engineering"]}.get(kit, [])
    return [t for t in base if t][:15]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_dir")
    ap.add_argument("--title", required=True)
    ap.add_argument("--thumb", default="split", help="wreck, split or fall")
    ap.add_argument("--publish-at", default="", help="RFC 3339 UTC; blank = public now")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    d = a.episode_dir
    sheet = json.load(open(os.path.join(d, "timed_sheet.json")))
    info = json.load(open(os.path.join(d, "episode.json")))
    text = description(sheet, info)
    open(os.path.join(d, "description.txt"), "w").write(text)
    print(f"TITLE: {a.title}\nTAGS: {tags(sheet)}\n\n{text}")
    if len(a.title) > 100:
        sys.exit("title over 100 characters")
    if a.dry_run:
        return
    from youtube_publisher import upload_video_to_youtube
    thumb = os.path.join(d, f"thumb_{a.thumb}.jpg")
    vid = upload_video_to_youtube(os.path.join(d, "episode.mp4"), a.title, text, tags(sheet),
                                  thumbnail_path=thumb if os.path.exists(thumb) else None,
                                  publish_at=a.publish_at or None)
    json.dump({"video_id": vid, "title": a.title, "publish_at": a.publish_at},
              open(os.path.join(d, "published.json"), "w"))


if __name__ == "__main__":
    main()
