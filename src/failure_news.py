"""
Failure news — engineering and industrial failures in this week's news.

The trend lane's first source. Google News search RSS, no API key, no new
dependency (the same feed trend_source.news_now already reads).

The channel never covers the live event itself. A headline only chooses WHICH
settled historical failure to tell: a bridge collapses this week, the video is
the 1967 Silver Bridge. Nothing about the live event's cause is known while it
is in the news, and this pipeline writes with free models and renders with AI
imagery, so the present-day story stays a one-line hook taken from the
headlines and everything else comes from the history (see
longform_llm.select_engineering_anchor and _now_rules).

When nothing usable is in the news, the lane falls back to this week's
anniversaries in the topic pool (topics.anniversary_topics), then to the
ordinary date rotation.
"""

import os
import re
import urllib.parse

from trend_source import NEWS_SEARCH_URL, _get, _items

# Searches, most specific first. Each names a failure, not a subject area:
# "bridge" alone returns ribbon cuttings and traffic reports.
QUERIES = [
    "bridge collapse",
    "building collapse",
    "dam failure",
    "dam collapse",
    "roof collapse",
    "crane collapse",
    "structural failure",
    "plant explosion",
    "refinery explosion",
    "factory explosion",
    "chemical leak",
    "gas explosion",
    "pipeline explosion",
    "mine collapse",
    "mine explosion",
    "train derailment",
    "ferry capsized",
    "ship sank",
    "tank rupture",
    "levee breach",
]

# A headline with any of these is about war, crime or a natural event, not
# a failure of something built. An explosion from a missile is not a plant
# explosion; a collapse in an earthquake is only ours once an inquiry blames
# the building, and that never happens inside a week.
EXCLUDE = (
    "missile", "drone", "airstrike", "air strike", "strike on", "shelling",
    "bomb", "attack", "terror", "shooting", "gunman", "war ", "troops",
    "military", "rocket fire", "earthquake", "hurricane", "typhoon",
    "cyclone", "tornado", "wildfire", "tsunami", "volcano", "stock",
    "shares", "market", "election", "poll", "nfl", "nba", "game",
    "anniversary", "years ago", "documentary", "movie", "film", "series",
    # a sea mine is a weapon, not a failure (first live run, 2026-10-16)
    "hitting mine", "hit a mine", "hitting a mine", "sea mine", "naval mine",
    # aftermath stories: the failure itself is not this week's news
    "reopen", "rebuilt", "rebuild", "celebrat", "demolition of",
)

DAYS = int(os.getenv("FAILURE_NEWS_DAYS", "7"))
PER_QUERY = 6


def _excluded(text: str) -> bool:
    low = f" {text.lower()} "
    return any(bad in low for bad in EXCLUDE)


def _key(headline: str) -> str:
    """Rough identity for one story across outlets: its longest words."""
    words = sorted(set(re.findall(r"[a-z]{5,}", headline.lower())),
                   key=len, reverse=True)
    return " ".join(sorted(words[:3]))


def get_failure_news(days: int = DAYS, queries=QUERIES, limit: int = 10):
    """[{"subject", "score", "query"}], most-reported first; [] when every
    feed is down or nothing qualifies. A story many outlets carry under
    several searches is a bigger story, which is what the score counts."""
    found = {}
    order = []
    for q in queries:
        try:
            items = list(_items(_get(NEWS_SEARCH_URL.format(
                q=urllib.parse.quote(f'"{q}"'), days=days))))
        except Exception as e:
            print(f"⚠️ Google News search ({q!r}) unavailable: {e}")
            continue
        for it in items[:PER_QUERY]:
            title = re.sub(r"\s+-\s+[^-]+$", "", it.get("title", "")).strip()
            if not title or _excluded(title):
                continue
            k = _key(title)
            if not k:
                continue
            if k in found:
                found[k]["score"] += 1
                continue
            found[k] = {"subject": title, "score": 1, "query": q}
            order.append(k)
    ranked = sorted((found[k] for k in order), key=lambda c: -c["score"])[:limit]
    print(f"📰 {len(ranked)} engineering-failure headline(s) in the last {days} days")
    for c in ranked[:8]:
        print(f"   [{c['score']}] {c['query']:<20} {c['subject'][:78]}")
    return ranked


if __name__ == "__main__":
    for row in get_failure_news():
        print(row)
