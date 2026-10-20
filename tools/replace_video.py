"""
Deletes a scheduled or private upload so a better cut can take its slot
(owner, 2026-10-21: the Hyatt episode, scheduled, gets the signature
preview). Refuses a public video: a public video's views and comments are
never thrown away.

    YT_CLIENT_SECRET_JSON=... YT_REFRESH_TOKEN=... python tools/replace_video.py VIDEO_ID
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))


def main(video_id):
    from youtube_publisher import get_authenticated_service
    yt = get_authenticated_service()
    got = yt.videos().list(part="status,snippet", id=video_id).execute().get("items", [])
    if not got:
        print(f"{video_id}: not found, nothing to replace")
        return
    st = got[0]["status"]
    title = got[0]["snippet"]["title"]
    if st.get("privacyStatus") == "public":
        sys.exit(f"{video_id} ({title!r}) is public: refusing to delete it")
    yt.videos().delete(id=video_id).execute()
    print(f"deleted {video_id} ({title!r}, {st.get('privacyStatus')}, publishAt {st.get('publishAt', '-')})")


if __name__ == "__main__":
    main(sys.argv[1])
