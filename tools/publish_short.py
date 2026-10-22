"""
Publishes a long video's highlight Short (tools/highlight_short.py): the
Short, a description pointing to the full video, the music credits CC BY
requires for the parts of the episode it was cut from, and a first comment
with the full video's link (held until the Short is public).

    python tools/publish_short.py SHORT_DIR EPISODE_DIR --title "..." --full VIDEO_ID [--publish-at T] [--dry-run]
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

CHANNEL = "The Point of Failure"


def music_credits(short, episode):
    """The credits of the tracks under the Short: its own (a scripted Short
    scores itself), or those of the parts it was cut from."""
    if short.get("music_credits"):
        return [c.strip() for c in short["music_credits"]]
    import score
    titles = [score.PARTS[p].split(" - ")[0] for p in short.get("parts", [])]
    return [c.strip() for c in episode.get("music_credits", [])
            if any(f'"{t}"' in c for t in titles)]


def description(short, episode, full_id):
    words = " ".join(x.strip() for x in short["top"].split("|") if x.strip()).split()
    words = [w if any(ch.isdigit() for ch in w) else w.lower() for w in words]   # I-35W stays
    top = " ".join(words)
    top = top[:1].upper() + top[1:]
    lines = [f"{top}.", "",
             f"The full story, step by step: https://www.youtube.com/watch?v={full_id}", "",
             "The 3D and 2D animations are reconstructions made from the investigation's "
             "findings; they show the mechanism, not footage of the event.", ""]
    credits = music_credits(short, episode)
    if credits:
        lines += ["MUSIC"] + credits + [""]
    lines += [f"{CHANNEL}: engineering disasters, explained.", "",
              "#shorts #engineering #engineeringdisaster"]
    return "\n".join(lines)[:4900]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("short_dir")
    ap.add_argument("episode_dir")
    ap.add_argument("--title", required=True)
    ap.add_argument("--full", required=True, help="the long video's id")
    ap.add_argument("--publish-at", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    short = json.load(open(os.path.join(a.short_dir, "short.json")))
    episode = json.load(open(os.path.join(a.episode_dir, "episode.json")))
    sheet = json.load(open(os.path.join(a.episode_dir, "timed_sheet.json")))
    text = description(short, episode, a.full)
    from publish_episode import tags
    tg = (["shorts"] + tags(sheet))[:15]
    print(f"TITLE: {a.title}\nTAGS: {tg}\n\n{text}")
    if len(a.title) > 100:
        sys.exit("title over 100 characters")
    if a.dry_run:
        return
    from youtube_publisher import upload_video_to_youtube
    vid = upload_video_to_youtube(os.path.join(a.short_dir, "short.mp4"), a.title, text, tg,
                                  first_comment=f"The full story, step by step: "
                                                f"https://www.youtube.com/watch?v={a.full}",
                                  publish_at=a.publish_at or None)
    json.dump({"video_id": vid, "title": a.title, "publish_at": a.publish_at},
              open(os.path.join(a.short_dir, "published.json"), "w"))


if __name__ == "__main__":
    main()
