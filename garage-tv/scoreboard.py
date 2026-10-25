#!/usr/bin/env python3
"""Scoreboard for the picture test: Nano Banana photo vs ChatGPT photo vs Sora moving video.

  python3 scoreboard.py --log TAG VIDEO_ID [SHORT_ID]   # after an upload: remember the YouTube ids
  YT_API_KEY=... python3 scoreboard.py                  # refresh view counts -> parked-fm/scoreboard.json

The daily job does both. View counts come from the YouTube Data API with a plain API key
(videos.list, 1 quota unit per 50 videos), which only sees public videos, so private uploads
show up with no numbers until they are made public. Music days and soundscape days are scored
separately as well as together, since they draw different audiences.

It also tracks the channel's road to the YouTube Partner Program: subscribers against the
500 (fan funding) and 1,000 (ads) goals, with one history point per day. When the YouTube
sign-in includes the analytics permission (get_youtube_token.py --renew), it adds watch hours
over the last 12 months and the subscribers each video brought in, which learn.py counts.
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


def api(endpoint, **params):
    q = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"https://www.googleapis.com/youtube/v3/{endpoint}?{q}", timeout=60) as r:
        return json.load(r).get("items", [])


def stats(ids, key):
    """({video id: (views, likes, privacy)} for the ids YouTube will show to an API key, channel id)."""
    out, channel = {}, None
    for i in range(0, len(ids), 50):
        for item in api("videos", part="snippet,statistics,status", id=",".join(ids[i:i + 50]), key=key):
            s = item.get("statistics", {})
            out[item["id"]] = (int(s.get("viewCount", 0)), int(s.get("likeCount", 0)),
                               item.get("status", {}).get("privacyStatus"))
            channel = channel or item.get("snippet", {}).get("channelId")
    return out, channel


ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"


def analytics():
    """(watch hours in the last 365 days, {video id: subscribers gained}) from YouTube Analytics,
    or None if the YouTube secrets or the analytics permission aren't there."""
    if not all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
        return None
    data = urllib.parse.urlencode({k: os.environ[v] for k, v in (
        ("client_id", "YT_CLIENT_ID"), ("client_secret", "YT_CLIENT_SECRET"), ("refresh_token", "YT_REFRESH_TOKEN"))}
        | {"grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data, timeout=60) as r:
        tok = json.load(r)
    if ANALYTICS_SCOPE not in tok.get("scope", "").split():
        return None
    end = dt.date.today()
    base = dict(ids="channel==MINE", startDate=(end - dt.timedelta(days=365)).isoformat(), endDate=end.isoformat())

    def report(**extra):
        q = urllib.parse.urlencode(base | extra)
        req = urllib.request.Request(f"https://youtubeanalytics.googleapis.com/v2/reports?{q}")
        req.add_header("Authorization", f"Bearer {tok['access_token']}")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r).get("rows") or []

    total = report(metrics="estimatedMinutesWatched")
    hours = round(total[0][0] / 60, 1) if total else 0.0
    rows = report(metrics="subscribersGained", dimensions="video", sort="-subscribersGained", maxResults=200)
    return hours, {r[0]: int(r[1]) for r in rows}


def channel_stats(channel, key):
    """Subscribers, total views and video count (YouTube rounds subscriber counts over 1,000)."""
    items = api("channels", part="statistics", id=channel, key=key) if channel and key else []
    if not items:
        return None
    s = items[0]["statistics"]
    return dict(subscribers=None if s.get("hiddenSubscriberCount") else int(s.get("subscriberCount", 0)),
                views=int(s.get("viewCount", 0)), videos=int(s.get("videoCount", 0)))


def refresh(key):
    log = [e for e in load() if e.get("maker") in NAMES and e.get("youtube")]
    ids = [e["youtube"] for e in log] + [e["short"] for e in log if e.get("short")]
    found, channel = stats(ids, key) if key and ids else ({}, None)
    try:
        studio = analytics()
    except Exception as e:  # numbers are a bonus; never fail the daily job over them
        print("analytics unavailable:", e)
        studio = None
    subs = studio[1] if studio else {}
    videos = []
    for e in log:
        views, likes, privacy = found.get(e["youtube"], (None, None, "private"))
        short_views = found.get(e.get("short"), (None,))[0]
        videos.append(dict(date=e["date"], title=e["title"], maker=e["maker"],
                           kind="music" if e["recipe"] == "lofi" else "soundscape",
                           youtube=e["youtube"], views=views, likes=likes, short_views=short_views,
                           # subscribers the video and its Short brought in
                           subscribers=subs.get(e["youtube"], 0) + subs.get(e.get("short"), 0) if studio else None,
                           public=privacy == "public"))

    def score(rows):
        live = [v for v in rows if v["views"] is not None]
        return dict(videos=len(rows), counted=len(live),
                    avg_views=round(sum(v["views"] for v in live) / len(live)) if live else None)

    board = {}
    for kind in ("all", "music", "soundscape"):
        rows = [v for v in videos if kind == "all" or v["kind"] == kind]
        board[kind] = {m: score([v for v in rows if v["maker"] == m]) for m in NAMES}
    now = dt.datetime.now(dt.timezone.utc)
    try:
        with open(OUT) as f:
            history = json.load(f).get("history", [])
    except (OSError, ValueError):
        history = []
    ch = channel_stats(channel, key)
    if ch and studio:
        ch["watch_hours"] = studio[0]
    if ch:
        history = [h for h in history if h["date"] != now.date().isoformat()] + [dict(date=now.date().isoformat(), **ch)]
    goals = dict(fan_funding=dict(subscribers=500, watch_hours=3000), ads=dict(subscribers=1000, watch_hours=4000))
    data = dict(updated=now.strftime("%Y-%m-%d %H:%M UTC"), names=NAMES, board=board,
                channel=history[-1] if history else None, goals=goals, history=history[-120:],
                videos=list(reversed(videos)))
    with open(OUT, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    for kind, row in board.items():
        print(kind, {NAMES[m]: s for m, s in row.items()})
    print("channel", data["channel"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--log", nargs="+", metavar="TAG VIDEO_ID [SHORT_ID]")
    a = ap.parse_args()
    if a.log:
        log_ids(*a.log[:3])
    else:
        refresh(os.environ.get("YT_API_KEY"))
