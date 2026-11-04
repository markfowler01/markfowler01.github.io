#!/usr/bin/env python3
"""The PARKED FM live stream (Mark, Nov 4: "the live does seem cool"): the newest Night Studio scene
(fire, rain, Kyleighanne or Wyatt nodding along) looping on screen, with the last several days' albums
(already carrying the soft rain and fireplace) playing in a shuffled order underneath, sent to YouTube
Live for a few hours.

Everything comes from the daily releases, so nothing new is made and nothing costs anything. One
evening block a day (6 pm to midnight Eastern) on GitHub's machines; if the stream catches on, the
same script can run 24/7 on a small rented server.

  YT_STREAM_KEY=... python3 live.py --hours 5.8               # go live
  python3 live.py --seconds 120 --out test.flv                # a 2-minute local test, nothing sent

The stream key is a password for the channel: it only ever comes from the environment and is never
printed.
"""
import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "https://github.com/markfowler01/markfowler01.github.io/releases/download"
INGEST = "rtmp://a.rtmp.youtube.com/live2/"


def ffmpeg():
    return shutil.which("ffmpeg") or __import__("imageio_ffmpeg").get_ffmpeg_exe()


def fetch(url, path):
    if not os.path.exists(path):
        urllib.request.urlretrieve(url, path)
    return path


def recent_days(log, n):
    """The newest n videos that have an album (lo-fi days), newest first."""
    with open(os.path.join(HERE, log)) as f:
        days = [e for e in json.load(f) if e.get("tag") and e.get("recipe") in ("lofi", "mix")]
    return days[::-1][:n]


def prepare(work, days):
    """The newest day's 60 s scene loop, re-encoded for streaming (1080p, a keyframe every 2 s, steady
    bitrate), and the albums of all the days, as a concat list in a shuffled order."""
    os.makedirs(work, exist_ok=True)
    ff = ffmpeg()
    newest = days[0]["tag"]
    zpath = fetch(f"{REPO}/{newest}/parked-fm-{newest}.zip", os.path.join(work, "kit.zip"))
    with zipfile.ZipFile(zpath) as z:
        name = next(n for n in z.namelist() if n.endswith("/loop.mp4"))
        with z.open(name) as src, open(os.path.join(work, "scene.mp4"), "wb") as dst:
            shutil.copyfileobj(src, dst)
    loop = os.path.join(work, "live-loop.mp4")
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", os.path.join(work, "scene.mp4"),
                    "-vf", "scale=1920:1080:flags=lanczos,fps=30,format=yuv420p", "-an",
                    "-c:v", "libx264", "-preset", "medium", "-profile:v", "high", "-b:v", "4500k",
                    "-maxrate", "4500k", "-bufsize", "9000k", "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
                    loop], check=True)
    albums = []
    for d in days:
        try:
            albums.append(fetch(f"{REPO}/{d['tag']}/music.m4a", os.path.join(work, f"{d['tag']}.m4a")))
        except Exception as e:  # an older day without its album in the release
            print(f"no album for {d['tag']}: {e}")
    if not albums:
        sys.exit("no albums to play")
    random.Random(newest).shuffle(albums)
    playlist = os.path.join(work, "playlist.txt")
    with open(playlist, "w") as f:
        f.writelines(f"file '{os.path.abspath(a)}'\n" for a in albums)
    print(f"scene from {newest} ({days[0].get('character') or 'no person'}), {len(albums)} albums")
    return loop, playlist


def stream(loop, playlist, seconds, out):
    """Send until `seconds` have passed; if the connection drops, reconnect and carry on."""
    ff = ffmpeg()
    end = time.time() + seconds
    while (left := end - time.time()) > 20:
        cmd = [ff, "-hide_banner", "-loglevel", "warning", "-stats_period", "60",
               "-re", "-stream_loop", "-1", "-i", loop,
               "-re", "-stream_loop", "-1", "-f", "concat", "-safe", "0", "-i", playlist,
               "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
               "-t", f"{left:.0f}", "-f", "flv", "-flvflags", "no_duration_filesize", out]
        started = time.time()
        code = subprocess.run(cmd).returncode
        if code == 0:
            break
        print(f"stream stopped (exit {code}) after {time.time() - started:.0f} s; reconnecting")
        time.sleep(5)


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--hours", type=float, default=5.8)
    ap.add_argument("--seconds", type=float, help="overrides --hours (tests)")
    ap.add_argument("--albums", type=int, default=10, help="how many recent days' albums to play")
    ap.add_argument("--log", default="published.json")
    ap.add_argument("--work", default="live-work")
    ap.add_argument("--out", help="a file to write instead of going live (tests)")
    a = ap.parse_args()
    out = a.out
    if not out:
        key = os.environ.get("YT_STREAM_KEY", "").strip()
        if not key:
            sys.exit("no YT_STREAM_KEY: add the channel's stream key as a GitHub secret")
        out = INGEST + key
    loop, playlist = prepare(a.work, recent_days(a.log, a.albums))
    seconds = a.seconds if a.seconds else a.hours * 3600
    print(f"live for {seconds / 3600:.2f} hours" if not a.out else f"test: {seconds:.0f} s to {a.out}")
    stream(loop, playlist, seconds, out)


if __name__ == "__main__":
    main()
