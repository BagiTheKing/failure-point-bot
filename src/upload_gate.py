"""
Channel spacing (owner, 2026-10-17): after any upload, a Short or a long
video, by the pipeline or by hand, the channel posts nothing else for
MIN_HOURS_BETWEEN_UPLOADS (48). Scheduled publishes count at their publish
time, so a long video's highlight Short scheduled 48 h after it holds the
next long video another 48 h.

The workflows run this in their small gate job, before anything is rendered:

    python src/upload_gate.py      # appends go=true|false to $GITHUB_OUTPUT

A run that only renders (SKIP_UPLOAD=1) always goes. PUBLISH_AT (RFC 3339)
checks the spacing at that time instead of now, for an upload scheduled to
go public then. IGNORE_SPACING=1 (a
manual run whose owner ticked the box) goes too. When the channel cannot be
read, a scheduled run stands down rather than risk breaking the rule; a
manual run goes, with a warning.
"""

import datetime
import os
import sys

MIN_HOURS = float(os.getenv("MIN_HOURS_BETWEEN_UPLOADS", "48"))
# a scheduled video goes public a few seconds after its time, so the slot 48 h
# after it would be missed by those seconds (the Hyatt cut, 2026-10-20)
GRACE = datetime.timedelta(minutes=2)


def _when(raw):
    try:
        return datetime.datetime.fromisoformat((raw or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def latest_post(videos):
    """(time, title) of the channel's latest post, a scheduled one included."""
    best = (None, "")
    for v in videos or []:
        times = [t for t in (_when(v.get("publishedAt")), _when(v.get("publishAt"))) if t]
        if times and (best[0] is None or max(times) > best[0]):
            best = (max(times), v.get("title", ""))
    return best


def next_free_slot(videos, hours=MIN_HOURS):
    when, _ = latest_post(videos)
    return when + datetime.timedelta(hours=hours) if when else None


def decide(videos, now=None, hours=MIN_HOURS):
    """(go, reason)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if hours <= 0:
        return True, "spacing disabled"
    when, title = latest_post(videos)
    if not when:
        return True, "no earlier post on the channel"
    slot = when + datetime.timedelta(hours=hours)
    if now >= slot - GRACE:
        return True, f"last post {(now - when).total_seconds() / 3600:.0f} h ago ({title[:60]!r})"
    return False, (f"last post {title[:60]!r} at {when:%Y-%m-%d %H:%M} UTC; the channel waits "
                   f"{hours:g} h, next slot {slot:%Y-%m-%d %H:%M} UTC")


def main():
    scheduled = os.getenv("GITHUB_EVENT_NAME") == "schedule"
    if os.getenv("SKIP_UPLOAD") == "1":
        go, reason = True, "dry run: nothing will be uploaded"
    elif os.getenv("IGNORE_SPACING") == "1" and not scheduled:
        go, reason = True, "spacing ignored by hand for this run"
    else:
        from channel_insights import fetch_recent_videos
        videos = fetch_recent_videos(limit=15)
        if videos is None:
            go = not scheduled
            reason = ("the channel could not be read: "
                      + ("a scheduled run stands down" if scheduled else "manual run goes anyway"))
        else:
            at = _when(os.getenv("PUBLISH_AT", "").strip())
            # the cut being replaced does not count against its own slot
            skip = os.getenv("IGNORE_VIDEO", "").strip()
            videos = [v for v in videos if v.get("videoId") != skip] if skip else videos
            go, reason = decide(videos, now=at if at and at.tzinfo else None)
    print(("✅ Go: " if go else "🛑 Standing down: ") + reason)
    out = os.getenv("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"go={'true' if go else 'false'}\n")
    return go


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
