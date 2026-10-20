"""
How much YouTube wants each candidate story (owner, 2026-10-20: "which is
the most famous of all time, and which is trending"): for each topic, the
views of the ten most-viewed videos about it ever (fame), and of the most
viewed published in the last 30 days (what is hot now).

    YT_CLIENT_SECRET_JSON=... YT_REFRESH_TOKEN=... python tools/topic_demand.py

Each topic costs about 200 units of the 10,000 daily YouTube quota (two
searches); 26 topics leave room for a day's uploads. Writes demand.md and
demand.json.
"""

import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

TOPICS = [
    ("Bridges", "Tacoma Narrows Bridge", "Tacoma Narrows bridge collapse"),
    ("Bridges", "Francis Scott Key Bridge", "Francis Scott Key Bridge collapse"),
    ("Bridges", "Silver Bridge", "Silver Bridge collapse 1967"),
    ("Bridges", "Quebec Bridge", "Quebec Bridge collapse 1907"),
    ("Bridges", "Morandi Bridge", "Morandi bridge collapse Genoa"),
    ("Buildings", "Surfside condo", "Surfside condo collapse Champlain Towers"),
    ("Buildings", "Sampoong store", "Sampoong department store collapse"),
    ("Buildings", "Rana Plaza", "Rana Plaza collapse"),
    ("Dams", "Banqiao Dam", "Banqiao dam failure"),
    ("Dams", "Teton Dam", "Teton dam failure"),
    ("Dams", "St. Francis Dam", "St Francis dam disaster"),
    ("Dams", "Vajont Dam", "Vajont dam disaster"),
    ("Tanks/pipes", "Boston Molasses Flood", "Boston molasses flood"),
    ("Tanks/pipes", "San Bruno pipeline", "San Bruno pipeline explosion"),
    ("Plants/reactors", "Chernobyl", "Chernobyl disaster explained"),
    ("Plants/reactors", "Piper Alpha", "Piper Alpha disaster"),
    ("Plants/reactors", "Three Mile Island", "Three Mile Island accident"),
    ("Aircraft", "de Havilland Comet", "de Havilland Comet crashes"),
    ("Aircraft", "Aloha 243", "Aloha Airlines flight 243"),
    ("Aircraft", "JAL 123", "Japan Airlines flight 123"),
    ("Spaceflight", "Challenger", "Challenger disaster explained"),
    ("Spaceflight", "Columbia", "Space Shuttle Columbia disaster"),
    ("Ships/offshore", "Titanic", "Titanic sinking explained"),
    ("Ships/offshore", "MS Estonia", "MS Estonia sinking"),
    ("Ships/offshore", "Deepwater Horizon", "Deepwater Horizon explosion"),
    ("Rail", "Eschede", "Eschede train disaster"),
    ("Ground/mines", "Aberfan", "Aberfan disaster"),
]


def _youtube():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    secret = json.loads(os.environ["YT_CLIENT_SECRET_JSON"])
    info = secret.get("web") or secret.get("installed")
    creds = Credentials(token=None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                        token_uri=info["token_uri"], client_id=info["client_id"],
                        client_secret=info["client_secret"],
                        scopes=["https://www.googleapis.com/auth/youtube.readonly"])
    return build("youtube", "v3", credentials=creds)


def top_views(yt, query, after=None):
    """[(views, title, channel, published)] of the most-viewed videos for a query."""
    q = dict(part="id", q=query, type="video", order="viewCount", maxResults=10, relevanceLanguage="en")
    if after:
        q["publishedAfter"] = after
    ids = [i["id"]["videoId"] for i in yt.search().list(**q).execute().get("items", [])]
    if not ids:
        return []
    got = yt.videos().list(part="snippet,statistics", id=",".join(ids)).execute().get("items", [])
    out = [(int(v["statistics"].get("viewCount", 0)), v["snippet"]["title"], v["snippet"]["channelTitle"],
            v["snippet"]["publishedAt"][:10]) for v in got]
    return sorted(out, reverse=True)


def _m(n):
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}k"


def main():
    yt = _youtube()
    after = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for family, name, query in TOPICS:
        try:
            ever, recent = top_views(yt, query), top_views(yt, query, after)
        except Exception as e:
            print(f"{name}: {type(e).__name__}: {str(e)[:120]}")
            continue
        rows.append({"family": family, "topic": name, "query": query,
                     "fame": sum(v for v, *_ in ever), "top": ever[:3],
                     "now": sum(v for v, *_ in recent), "recent": recent[:3],
                     "million_plus": sum(1 for v, *_ in ever if v >= 1e6)})
        print(f"{name:<26} ever {_m(rows[-1]['fame']):>7}  last 30 days {_m(rows[-1]['now']):>6}")
    json.dump(rows, open("demand.json", "w"), indent=1, ensure_ascii=False)
    lines = ["# Topic demand on YouTube", "",
             "Fame: views of the 10 most-viewed videos ever. Now: views of the 10 most-viewed "
             "published in the last 30 days.", "",
             "| Family | Topic | Fame | 1M+ videos | Now | Top video now |", "|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: -r["fame"]):
        top_now = f"{r['recent'][0][1][:50]} ({_m(r['recent'][0][0])})" if r["recent"] else "none"
        lines.append(f"| {r['family']} | {r['topic']} | {_m(r['fame'])} | {r['million_plus']} | "
                     f"{_m(r['now'])} | {top_now} |")
    lines += ["", "## Biggest videos per topic", ""]
    for r in sorted(rows, key=lambda r: -r["fame"]):
        lines.append(f"**{r['topic']}**: " + "; ".join(f"{t[:60]} ({c}, {_m(v)}, {d})"
                                                        for v, t, c, d in r["top"]))
    open("demand.md", "w").write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
