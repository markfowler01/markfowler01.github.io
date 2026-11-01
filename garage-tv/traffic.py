#!/usr/bin/env python3
"""Where PARKED FM's views come from, from YouTube Analytics (needs the YT_* secrets with the
analytics permission). Prints the last 28 days: views by traffic source, by day, per video (with
average view time), and thumbnail impressions and click rate when YouTube reports them.

  python3 traffic.py
"""
import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request


def token():
    data = urllib.parse.urlencode({k: os.environ[v] for k, v in (
        ("client_id", "YT_CLIENT_ID"), ("client_secret", "YT_CLIENT_SECRET"), ("refresh_token", "YT_REFRESH_TOKEN"))}
        | {"grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data, timeout=60) as r:
        return json.load(r)["access_token"]


def main():
    tok = token()
    end = dt.date.today()
    base = dict(ids="channel==MINE", startDate=(end - dt.timedelta(days=28)).isoformat(), endDate=end.isoformat())

    def report(title, **extra):
        q = urllib.parse.urlencode(base | extra)
        req = urllib.request.Request(f"https://youtubeanalytics.googleapis.com/v2/reports?{q}")
        req.add_header("Authorization", f"Bearer {tok}")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            print(f"\n== {title}: not available ({e.code}: {e.read()[:200]!r})")
            return
        print(f"\n== {title}")
        print(" | ".join(h["name"] for h in data.get("columnHeaders", [])))
        for row in data.get("rows") or []:
            print(" | ".join(str(x) for x in row))

    report("Views by traffic source", metrics="views,estimatedMinutesWatched",
           dimensions="insightTrafficSourceType", sort="-views")
    report("Views by day", metrics="views,estimatedMinutesWatched,subscribersGained", dimensions="day", sort="day")
    report("Per video", metrics="views,estimatedMinutesWatched,averageViewDuration,likes,subscribersGained",
           dimensions="video", sort="-views", maxResults=60)
    report("Thumbnail impressions and click rate per video",
           metrics="videoThumbnailImpressions,videoThumbnailImpressionsClickRate,views",
           dimensions="video", sort="-videoThumbnailImpressions", maxResults=60)
    report("Search terms that found us", metrics="views", dimensions="insightTrafficSourceDetail",
           filters="insightTrafficSourceType==YT_SEARCH", sort="-views", maxResults=25)
    report("Views by country", metrics="views", dimensions="country", sort="-views", maxResults=10)


if __name__ == "__main__":
    main()
