"""The real photo a Short ends on, fetched on the runner.

    python tools/short_photo.py script.json photo.jpg

In order of trust: the exact Commons file the script names ("photo_file"),
the lead image of the event's Wikipedia article ("photo_article": the one
picture its editors chose for the whole event), then a Commons search
("photo_search") whose result must carry the search's names. A bare search
put a 1922 Yellowstone road guide under the Teton Dam's death toll. Writes
photo.jpg and, beside it, photo.json: what was fetched and its credit."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from archive_engine import (article_lead_image, commons_file, download_archival_image,  # noqa: E402
                            format_credit, search_commons)
from episode import _names_match  # noqa: E402


def pick(script):
    """(candidate, how it was found), or (None, None)."""
    if script.get("photo_file"):
        c = commons_file(script["photo_file"])
        if c:
            return c, "file"
    if script.get("photo_article"):
        c = article_lead_image(script["photo_article"])
        if c:
            return c, "article"
    q = script.get("photo_search")
    if q:
        for c in search_commons(q, limit=8):
            if _names_match(q, c):
                return c, "search"
    return None, None


def main(script_path, out):
    script = json.load(open(script_path))
    c, how = pick(script)
    if not c or not download_archival_image(c, out, 0, 0, fit=lambda im, w, h: im):
        sys.exit("no photo for the Short: name a photo_file or photo_article in its script")
    info = {"title": c.get("title"), "license": c.get("license"), "artist": c.get("artist"),
            "about": c.get("about"), "found_by": how, "credit": format_credit(c)}
    json.dump(info, open(os.path.splitext(out)[0] + ".json", "w"), indent=1, ensure_ascii=False)
    print(f"photo ({how}): {c.get('title')} | {c.get('license')}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
