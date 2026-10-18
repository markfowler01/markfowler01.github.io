#!/usr/bin/env python3
"""Build a music-day album from real songs in garage-tv/music/ (e.g. downloaded from the
YouTube Audio Library), instead of generated music.

Songs are shuffled (a different order every video), levelled to the same loudness, given a
short fade-in, and joined with a few seconds of silence. Nothing else is mixed in: no hiss,
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
EXTS = ("*.mp3", "*.m4a", "*.wav", "*.aac", "*.ogg", "*.flac")
MIN_TRACKS = 8  # music days stay off until the library has at least this many songs
SR = 44100


def library():
    return sorted(p for e in EXTS for p in glob.glob(os.path.join(LIBRARY, e)))


def music_ready(day=None):
    """Music days run only with enough songs, and only while their licence covers new videos:
    set MUSIC_UNTIL=YYYY-MM-DD (e.g. the last day of an Epidemic Sound trial or subscription)
    and music days stop by themselves after that date."""
    until = os.environ.get("MUSIC_UNTIL", "").strip()
    if until:
        today = day or datetime.date.today()
        if today > datetime.date.fromisoformat(until):
            return False
    return len(library()) >= MIN_TRACKS


def wav_seconds(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--min-minutes", type=float, default=30, help="repeat the shuffled list until at least this long")
    ap.add_argument("--max-minutes", type=float, default=90, help="stop adding songs past this length")
    ap.add_argument("--gap", type=float, default=3.0, help="seconds of silence between songs")
    ap.add_argument("--bitrate", default="192k")
    ap.add_argument("--out", default="music.m4a")
    args = ap.parse_args()

    songs = library()
    if not songs:
        raise SystemExit(f"no songs in {LIBRARY}")
    rng = random.Random(args.seed)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    tmp = tempfile.mkdtemp(prefix="playlist-")
    try:
        silence = os.path.join(tmp, "silence.wav")
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo",
                        "-t", str(args.gap), "-c:a", "pcm_s16le", silence], check=True)
        order, total, starts, parts = [], 0.0, [], []
        while total < args.min_minutes * 60 or not order:
            batch = songs[:]
            rng.shuffle(batch)
            if order and batch[0] == order[-1] and len(batch) > 1:
                batch[0], batch[1] = batch[1], batch[0]  # never the same song twice in a row
            for song in batch:
                if total >= args.max_minutes * 60:
                    break
                part = os.path.join(tmp, f"{len(order):03d}.wav")
                # same loudness for every song (background-music level), a soft start, nothing added
                subprocess.run([ff, "-y", "-loglevel", "error", "-i", song, "-vn",
                                "-af", "loudnorm=I=-18:TP=-2:LRA=11,afade=t=in:d=0.6",
                                "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", part], check=True)
                starts.append(round(total, 2))
                order.append(song)
                parts += [part, silence]
                total += wav_seconds(part) + args.gap
                print(f"  {len(order):2d}. {os.path.basename(song)}")
        listing = os.path.join(tmp, "list.txt")
        with open(listing, "w") as f:
            f.writelines(f"file '{p}'\n" for p in parts)
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing,
                        "-c:a", "aac", "-b:a", args.bitrate, "-movflags", "+faststart", args.out], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    with open(os.path.splitext(args.out)[0] + ".tracks.json", "w") as f:
        json.dump(dict(minutes=round(total / 60, 3), track_starts=starts,
                       songs=[os.path.basename(s) for s in order]), f, indent=1)
    print(f"album: {len(order)} songs, {total / 60:.1f} min -> {args.out}")


if __name__ == "__main__":
    main()
