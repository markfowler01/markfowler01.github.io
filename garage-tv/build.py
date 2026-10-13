#!/usr/bin/env python3
"""Build a finished garage-TV video of any length: visual loop + ambience.

  python3 build.py --minutes 480 --image stills/bay-dusk.webp     # 8 hours
  python3 build.py --minutes 60 --theme amber --compressor         # generated scene

How it stays fast at 8 hours:
  1. make_ambience.py renders one seamless audio chunk (--audio-minutes, default 10)
  2. one visual loop is rendered (--loop-seconds, default 60)
  3. ffmpeg repeats the video loop with stream copy (no re-encode) and
     concatenates the raw audio chunks, encoding the AAC track once.

Visual sources, pick one:
  --image photo.jpg    slow drift + zoom over a still (make_still_loop.py)
  --footage clip.mp4   your own video clip, looped as-is
  (neither)            the generated neon-garage scene (make_visuals.py)
"""
import argparse
import math
import os
import subprocess
import sys

import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def probe_duration(ffmpeg, path):
    """Seconds of media in `path`, read from ffmpeg's banner (no ffprobe needed)."""
    r = subprocess.run([ffmpeg, "-i", path], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            hms = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = hms.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return None


def concat_list(path, file, repeats):
    with open(path, "w") as f:
        for _ in range(repeats):
            f.write(f"file '{os.path.abspath(file)}'\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=10, help="total length of the finished video")
    ap.add_argument("--theme", default="cyan")
    ap.add_argument("--loop-seconds", type=float, default=60)
    ap.add_argument("--audio-minutes", type=float, default=10, help="length of the seamless audio chunk")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--compressor", action="store_true")
    ap.add_argument("--footage", help="use this video clip as the visual loop")
    ap.add_argument("--image", help="use this photo (slow drift + zoom) as the visual loop")
    ap.add_argument("--workdir", default=os.path.join(HERE, "out"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    os.makedirs(args.workdir, exist_ok=True)
    if args.image:
        name = os.path.splitext(os.path.basename(args.image))[0]
    elif args.footage:
        name = os.path.splitext(os.path.basename(args.footage))[0]
    else:
        name = args.theme
    total_s = args.minutes * 60
    audio_min = min(args.audio_minutes, args.minutes)
    out = args.out or os.path.join(args.workdir, f"garage-{name}-{int(args.minutes)}m.mp4")
    wav = os.path.join(args.workdir, f"ambience-{int(audio_min)}m-seamless.wav")
    loop = args.footage or os.path.join(args.workdir, f"loop-{name}.mp4")

    # 1. audio chunk (seamless so it can be repeated)
    amb = [sys.executable, os.path.join(HERE, "make_ambience.py"), "--minutes", str(audio_min),
           "--seamless", "--out", wav]
    if args.compressor:
        amb.append("--compressor")
    run(amb)

    # 2. one visual loop
    if args.image:
        run([sys.executable, os.path.join(HERE, "make_still_loop.py"), "--image", args.image,
             "--seconds", str(args.loop_seconds), "--width", str(args.width), "--height", str(args.height),
             "--out", loop])
    elif not args.footage:
        run([sys.executable, os.path.join(HERE, "make_visuals.py"), "--seconds", str(args.loop_seconds),
             "--theme", args.theme, "--width", str(args.width), "--height", str(args.height), "--out", loop])

    # 3. repeat both to the target length; video is stream-copied, audio encoded once
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    loop_len = probe_duration(ffmpeg, loop) or args.loop_seconds
    v_list = os.path.join(args.workdir, "video-list.txt")
    a_list = os.path.join(args.workdir, "audio-list.txt")
    concat_list(v_list, loop, math.ceil(total_s / loop_len))
    concat_list(a_list, wav, math.ceil(args.minutes / audio_min))
    run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", v_list,
         "-f", "concat", "-safe", "0", "-i", a_list,
         "-map", "0:v:0", "-map", "1:a:0", "-t", str(total_s),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])
    size_mb = os.path.getsize(out) / 1e6
    print(f"\nDONE: {out}  ({size_mb:.0f} MB, {args.minutes:g} min)")


if __name__ == "__main__":
    main()
