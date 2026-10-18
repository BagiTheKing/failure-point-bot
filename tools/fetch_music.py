"""
Downloads Kevin MacLeod tracks (incompetech.com, CC BY 4.0) into music/ with
the credit sidecar their licence requires (music/README.md), by title:

    python tools/fetch_music.py "Mechanolith" "Volatile Reaction"
    python tools/fetch_music.py --list dark      # titles whose feel matches

Titles come from incompetech's own catalogue (pieces.json), so a misspelt or
missing title is reported rather than guessed.
"""

import json
import os
import sys
import urllib.parse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
MUSIC = os.path.join(HERE, "..", "music")
CATALOGUE = "https://incompetech.com/music/royalty-free/pieces.json"
MP3 = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
UA = {"User-Agent": "PointOfFailureBot/1.0 (https://github.com/BagiTheKing/failure-point-bot)"}

CREDIT = ('"{title}" Kevin MacLeod (incompetech.com)\n'
          "Licensed under Creative Commons: By Attribution 4.0 License\n"
          "http://creativecommons.org/licenses/by/4.0/")


def catalogue():
    try:
        return requests.get(CATALOGUE, headers=UA, timeout=60).json()
    except Exception as e:
        print(f"catalogue unavailable ({type(e).__name__}: {e})")
        return []


def fetch(title, pieces):
    entry = next((p for p in pieces if p.get("title", "").lower() == title.lower()), None)
    name = (entry or {}).get("filename") or f"{title}.mp3"
    title = (entry or {}).get("title", title)
    out = os.path.join(MUSIC, f"{title} - Kevin MacLeod.mp3")
    if os.path.exists(out):
        print(f"have: {title}")
        return out
    r = requests.get(MP3 + urllib.parse.quote(name), headers=UA, timeout=120)
    if r.status_code != 200 or len(r.content) < 100_000:
        print(f"not found: {title} ({r.status_code})")
        return None
    open(out, "wb").write(r.content)
    open(out + ".attribution.txt", "w").write(CREDIT.format(title=title) + "\n")
    feel = ", ".join(x for x in [(entry or {}).get("feel"), (entry or {}).get("genre")] if x)
    print(f"got: {title} ({len(r.content) // 1024} KB) {feel}")
    return out


if __name__ == "__main__":
    pieces = catalogue()
    if sys.argv[1:2] == ["--list"]:
        want = (sys.argv[2] if len(sys.argv) > 2 else "dark").lower()
        for p in pieces:
            if want in json.dumps(p).lower():
                print(f"{p.get('title')} | {p.get('feel')} | {p.get('genre')} | {p.get('length')}")
    else:
        for t in sys.argv[1:]:
            fetch(t, pieces)
