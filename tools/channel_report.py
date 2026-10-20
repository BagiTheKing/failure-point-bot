"""
How the channel's videos are doing, for the check-ins (owner, 2026-10-20:
"what other data do you need from me to pull?"): per video, views, watch
time, average view duration and percentage, likes, subscribers gained, the
traffic sources, and the retention curve (where viewers leave).

    YT_CLIENT_SECRET_JSON=... YT_REFRESH_TOKEN=... python tools/channel_report.py [--days 28]

Public counts come from the Data API; the rest from the YouTube Analytics
API, which needs the token minted with yt-analytics.readonly
(tools/get_youtube_refresh_token.py) and the Analytics API enabled on the
Cloud project. Without it the report says so and gives the public counts.
Impressions and click-through rate are not in any API: they stay in Studio.
Writes report.md.
"""

import argparse
import datetime
import json
import os

READ = ["https://www.googleapis.com/auth/youtube.readonly"]
ANALYTICS = ["https://www.googleapis.com/auth/yt-analytics.readonly"]


def _credentials(scopes):
    """Separate credentials per API: an old token without the analytics
    scope still reads the public counts."""
    from google.oauth2.credentials import Credentials
    secret = json.loads(os.environ["YT_CLIENT_SECRET_JSON"])
    info = secret.get("web") or secret.get("installed")
    return Credentials(token=None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                       token_uri=info["token_uri"], client_id=info["client_id"],
                       client_secret=info["client_secret"], scopes=scopes)


def _mmss(s):
    s = int(round(s or 0))
    return f"{s // 60}:{s % 60:02d}"


def videos(yt):
    ch = yt.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=25).execute()
    ids = [i["contentDetails"]["videoId"] for i in items.get("items", [])]
    got = yt.videos().list(part="snippet,statistics,contentDetails,status", id=",".join(ids)).execute() if ids else {}
    return ch, got.get("items", [])


def analytics(ya, vid, start, end):
    q = dict(ids="channel==MINE", startDate=start, endDate=end, filters=f"video=={vid}")
    out = {}
    r = ya.reports().query(metrics="views,estimatedMinutesWatched,averageViewDuration,"
                           "averageViewPercentage,subscribersGained,likes,shares", **q).execute()
    if r.get("rows"):
        out["totals"] = dict(zip([h["name"] for h in r["columnHeaders"]], r["rows"][0]))
    r = ya.reports().query(metrics="views", dimensions="insightTrafficSourceType",
                           sort="-views", **q).execute()
    out["sources"] = [(row[0], row[1]) for row in r.get("rows", [])]
    r = ya.reports().query(metrics="audienceWatchRatio", dimensions="elapsedVideoTimeRatio", **q).execute()
    out["retention"] = [(row[0], row[1]) for row in r.get("rows", [])]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=28)
    a = ap.parse_args()
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=_credentials(READ))
    ch, vids = videos(yt)
    st = ch["statistics"]
    lines = [f"# {ch['snippet']['title'].strip()}: {datetime.date.today()}", "",
             f"Subscribers {st.get('subscriberCount')} · views {st.get('viewCount')} · "
             f"videos {st.get('videoCount')}", ""]
    end = datetime.date.today()
    start = (end - datetime.timedelta(days=a.days)).isoformat()
    try:
        ya = build("youtubeAnalytics", "v2", credentials=_credentials(ANALYTICS))
        ya.reports().query(ids="channel==MINE", startDate=start, endDate=end.isoformat(),
                           metrics="views").execute()
    except Exception as e:
        ya = None
        lines += [f"Analytics unavailable ({type(e).__name__}: {str(e)[:160]}). Mint the token again "
                  "with tools/get_youtube_refresh_token.py and enable the YouTube Analytics API.", ""]
    for v in vids:
        s, sn = v["statistics"], v["snippet"]
        lines += [f"## {sn['title']}", f"https://youtu.be/{v['id']} · {v['status'].get('privacyStatus')} · "
                  f"published {sn['publishedAt'][:16].replace('T', ' ')} UTC · length "
                  f"{v['contentDetails']['duration'][2:].lower()}",
                  f"Views {s.get('viewCount', 0)} · likes {s.get('likeCount', 0)} · "
                  f"comments {s.get('commentCount', 0)}"]
        if ya:
            try:
                an = analytics(ya, v["id"], start, end.isoformat())
            except Exception as e:
                lines += [f"(no analytics: {type(e).__name__})", ""]
                continue
            t = an.get("totals")
            if t:
                lines += [f"Watch time {t['estimatedMinutesWatched']:.0f} min · average view "
                          f"{_mmss(t['averageViewDuration'])} ({t['averageViewPercentage']:.0f}% of it) · "
                          f"subscribers +{t['subscribersGained']:.0f} · shares {t['shares']:.0f}"]
            if an["sources"]:
                lines += ["Traffic: " + ", ".join(f"{k.lower().replace('_', ' ')} {n:.0f}"
                                                  for k, n in an["sources"])]
            ret = an["retention"]
            if ret:
                pts = [ret[min(len(ret) - 1, int(len(ret) * k / 10))] for k in range(10)]
                lines += ["Still watching: " + " · ".join(f"{int(r * 100)}% in: {w * 100:.0f}%"
                                                          for r, w in pts)]
        lines += [""]
    lines += ["Impressions and click-through rate are only in YouTube Studio (Analytics → Reach)."]
    text = "\n".join(lines)
    open("report.md", "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
