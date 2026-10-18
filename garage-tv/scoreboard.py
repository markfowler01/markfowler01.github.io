#!/usr/bin/env python3
"""Scoreboard for the picture test: Nano Banana photo vs ChatGPT photo vs Sora moving video.

  python3 scoreboard.py --log TAG VIDEO_ID [SHORT_ID]   # after an upload: remember the YouTube ids
  YT_API_KEY=... python3 scoreboard.py                  # refresh view counts -> parked-fm/scoreboard.json

The daily job does both. View counts come from the YouTube Data API with a plain API key
(videos.list, 1 quota unit per 50 videos), which only sees public videos, so private uploads
show up with no numbers until they are made public. Music days and soundscape days are scored
separately as well as together, since they draw different audiences.
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLISHED = os.path.join(HERE, "published.json")
OUT = os.path.join(HERE, "..", "parked-fm", "scoreboard.json")
NAMES = {"gemini": "Nano Banana", "openai": "ChatGPT", "sora": "Sora (moving)"}


def load():
    with open(PUBLISHED) as f:
        return json.load(f)


def save(log):
    with open(PUBLISHED, "w") as f:
        json.dump(log, f, indent=2)
        f.write("\n")


def log_ids(tag, video_id, short_id=None):
    log = load()
    for e in reversed(log):
        if e.get("tag") == tag:
            e["youtube"] = video_id
            if short_id:
                e["short"] = short_id
            save(log)
            print(f"{tag}: youtube {video_id}" + (f", short {short_id}" if short_id else ""))
            return
    sys.exit(f"no published.json entry with tag {tag}")


def stats(ids, key):
    """{video id: (views, likes, privacy)} for the ids YouTube will show to an API key."""
    out = {}
    for i in range(0, len(ids), 50):
        q = urllib.parse.urlencode({"part": "statistics,status", "id": ",".join(ids[i:i + 50]), "key": key})
        with urllib.request.urlopen(f"https://www.googleapis.com/youtube/v3/videos?{q}", timeout=60) as r:
            for item in json.load(r).get("items", []):
                s = item.get("statistics", {})
                out[item["id"]] = (int(s.get("viewCount", 0)), int(s.get("likeCount", 0)),
                                   item.get("status", {}).get("privacyStatus"))
    return out


def refresh(key):
    log = [e for e in load() if e.get("maker") in NAMES and e.get("youtube")]
    ids = [e["youtube"] for e in log] + [e["short"] for e in log if e.get("short")]
    found = stats(ids, key) if key and ids else {}
    videos = []
    for e in log:
        views, likes, privacy = found.get(e["youtube"], (None, None, "private"))
        short_views = found.get(e.get("short"), (None,))[0]
        videos.append(dict(date=e["date"], title=e["title"], maker=e["maker"],
                           kind="music" if e["recipe"] == "lofi" else "soundscape",
                           youtube=e["youtube"], views=views, likes=likes, short_views=short_views,
                           public=privacy == "public"))

    def score(rows):
        live = [v for v in rows if v["views"] is not None]
        return dict(videos=len(rows), counted=len(live),
                    avg_views=round(sum(v["views"] for v in live) / len(live)) if live else None)

    board = {}
    for kind in ("all", "music", "soundscape"):
        rows = [v for v in videos if kind == "all" or v["kind"] == kind]
        board[kind] = {m: score([v for v in rows if v["maker"] == m]) for m in NAMES}
    data = dict(updated=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                names=NAMES, board=board, videos=list(reversed(videos)))
    with open(OUT, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    for kind, row in board.items():
        print(kind, {NAMES[m]: s for m, s in row.items()})


if __name__ == "__main__":
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--log", nargs="+", metavar="TAG VIDEO_ID [SHORT_ID]")
    a = ap.parse_args()
    if a.log:
        log_ids(*a.log[:3])
    else:
        refresh(os.environ.get("YT_API_KEY"))
