"""
Lists the free footage that exists for a story, so a human can see what the
episode's cold open can use: Wikimedia Commons (category members and search)
and the Internet Archive (with each item's licence).

    python tools/footage_probe.py "I-35W Mississippi River bridge collapse"
"""

import json
import sys

import requests

UA = {"User-Agent": "FailurePointBot/1.0 (https://github.com/BagiTheKing/failure-point-bot)"}
COMMONS = "https://commons.wikimedia.org/w/api.php"


def commons_category(cat):
    r = requests.get(COMMONS, headers=UA, timeout=30, params={
        "action": "query", "format": "json", "generator": "categorymembers",
        "gcmtitle": f"Category:{cat}", "gcmtype": "file", "gcmlimit": 500,
        "prop": "videoinfo|imageinfo", "viprop": "url|size|mime|extmetadata",
        "iiprop": "mime"}).json()
    for p in (r.get("query") or {}).get("pages", {}).values():
        info = (p.get("videoinfo") or p.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "")
        if mime.startswith("video") or p["title"].lower().endswith((".webm", ".ogv", ".mp4")):
            meta = info.get("extmetadata") or {}
            print(f"  COMMONS {p['title']} | {info.get('duration')} s | "
                  f"{(meta.get('LicenseShortName') or {}).get('value')} | {info.get('url')}")


def commons_search(q):
    r = requests.get(COMMONS, headers=UA, timeout=30, params={
        "action": "query", "format": "json", "list": "search", "srnamespace": 6,
        "srsearch": f"filetype:video {q}", "srlimit": 30}).json()
    for s in (r.get("query") or {}).get("search", []):
        print(f"  COMMONS-SEARCH {s['title']}")


def archive(q):
    r = requests.get("https://archive.org/advancedsearch.php", headers=UA, timeout=30, params={
        "q": f"({q}) AND mediatype:movies", "fl[]": ["identifier", "title", "licenseurl", "date"],
        "rows": 40, "output": "json"}).json()
    for d in r.get("response", {}).get("docs", []):
        print(f"  ARCHIVE {d.get('identifier')} | {d.get('title')} | {d.get('date')} | "
              f"licence: {d.get('licenseurl')}")


if __name__ == "__main__":
    topic = sys.argv[1]
    name = topic.replace(" collapse", "")
    for label, fn, arg in (("category", commons_category, topic.replace(" ", "_")),
                           ("category", commons_category, name.replace(" ", "_")),
                           ("search", commons_search, topic),
                           ("search", commons_search, f"{name} surveillance"),
                           ("archive", archive, f'"{name}"'),
                           ("archive", archive, f"{name} collapse camera")):
        print(f"== {label}: {arg}")
        try:
            fn(arg)
        except Exception as e:
            print(f"  failed: {type(e).__name__}: {e}")
