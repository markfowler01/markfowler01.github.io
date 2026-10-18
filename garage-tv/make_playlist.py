#!/usr/bin/env python3
"""Build a music-day album from real songs in garage-tv/music/ (e.g. downloaded from the
YouTube Audio Library), instead of generated music.

Each album takes songs that have never been in a video yet (published.json remembers which
songs every video used), so every video gets new music until the library runs out; only then
do the least-used songs come back. Songs are levelled to the same loudness, given a short
fade-in, and joined with a few seconds of silence. Nothing else is mixed in: no hiss,
crackle, rain or noise. The album is AAC, ready to loop under the video, and a .tracks.json
next to it lists where each song starts.

  python3 make_playlist.py --seed 7 --out music.m4a
"""
import argparse
import datetime
import glob
import json
import os
import random
import shutil
import subprocess
import tempfile
import wave

import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
LIBRARY = os.path.join(HERE, "music")
# Songs whose licence only covers videos published before a date (e.g. an Epidemic Sound trial)
# go in music/epidemic/; they drop out after MUSIC_UNTIL. Free-forever songs (Pixabay, YouTube
# Audio Library) go straight in music/ and always play.
LIMITED = os.path.join(LIBRARY, "epidemic")
EXTS = ("*.mp3", "*.m4a", "*.wav", "*.aac", "*.ogg", "*.flac")
MIN_TRACKS = 8  # music days stay off until the library has at least this many songs
SR = 44100


def limited_ok(day=None):
    """True while the time-limited songs (music/epidemic) may go in new videos:
    up to and including MUSIC_UNTIL (YYYY-MM-DD); always, if it isn't set."""
    until = os.environ.get("MUSIC_UNTIL", "").strip()
    return not until or (day or datetime.date.today()) <= datetime.date.fromisoformat(until)


def library(day=None):
    folders = [LIBRARY] + ([LIMITED] if limited_ok(day) else [])
    return sorted(p for d in folders for e in EXTS for p in glob.glob(os.path.join(d, e)))


def music_ready(day=None):
    """Music days run only when at least MIN_TRACKS songs are usable today."""
    return len(library(day)) >= MIN_TRACKS


def wav_seconds(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def song_history():
    """{song file name: (times used, index of the last video it was in)} from published.json."""
    path = os.path.join(HERE, "published.json")
    seen = {}
    if os.path.exists(path):
        with open(path) as f:
            for i, e in enumerate(json.load(f)):
                for name in e.get("songs") or []:
                    n, _ = seen.get(name, (0, -1))
                    seen[name] = (n + 1, i)
    return seen


def pick_songs(songs, rng):
    """Every song plays once before any song plays twice: songs never used come first (in a
    random order), then the ones used fewest times and longest ago."""
    seen = song_history()
    keyed = [(seen.get(os.path.basename(s), (0, -1)), rng.random(), s) for s in songs]
    return [s for _, _, s in sorted(keyed)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--minutes", type=float, default=35, help="album length; it loops under the video")
    ap.add_argument("--gap", type=float, default=3.0, help="seconds of silence between songs")
    ap.add_argument("--bitrate", default="192k")
    ap.add_argument("--out", default="music.m4a")
    args = ap.parse_args()

    songs = library()
    if not songs:
        raise SystemExit(f"no songs in {LIBRARY}")
    rng = random.Random(args.seed)
    queue = pick_songs(songs, rng)
    history = song_history()
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    tmp = tempfile.mkdtemp(prefix="playlist-")
    try:
        silence = os.path.join(tmp, "silence.wav")
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo",
                        "-t", str(args.gap), "-c:a", "pcm_s16le", silence], check=True)
        order, total, starts, parts = [], 0.0, [], []
        while total < args.minutes * 60:
            song = queue[len(order) % len(queue)]  # a small library wraps around inside one album
            part = os.path.join(tmp, f"{len(order):03d}.wav")
            # same loudness for every song (background-music level), a soft start, nothing added
            subprocess.run([ff, "-y", "-loglevel", "error", "-i", song, "-vn",
                            "-af", "loudnorm=I=-18:TP=-2:LRA=11,afade=t=in:d=0.6",
                            "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", part], check=True)
            starts.append(round(total, 2))
            order.append(song)
            parts += [part, silence]
            total += wav_seconds(part) + args.gap
            used = history.get(os.path.basename(song), (0,))[0]
            print(f"  {len(order):2d}. {os.path.basename(song)}" + ("" if not used else f"  (played in {used} earlier video(s))"))
        listing = os.path.join(tmp, "list.txt")
        with open(listing, "w") as f:
            f.writelines(f"file '{p}'\n" for p in parts)
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing,
                        "-c:a", "aac", "-b:a", args.bitrate, "-movflags", "+faststart", args.out], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    names = [os.path.basename(s) for s in order]
    with open(os.path.splitext(args.out)[0] + ".tracks.json", "w") as f:
        json.dump(dict(minutes=round(total / 60, 3), track_starts=starts, songs=names), f, indent=1)
    fresh_left = sum(1 for s in songs if os.path.basename(s) not in history and os.path.basename(s) not in names)
    print(f"album: {len(order)} songs, {total / 60:.1f} min -> {args.out}; "
          f"{fresh_left} never-played songs left in the library")
    if fresh_left < 10:
        print("::warning::fewer than 10 never-played songs left; add more to garage-tv/music for new music every video")


if __name__ == "__main__":
    main()
