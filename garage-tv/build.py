#!/usr/bin/env python3
"""Build a finished garage-TV video: visual loop + ambience, any length.

  python3 build.py --minutes 60 --theme amber --out garage-amber-1h.mp4

Steps:
  1. make_ambience.py renders --minutes of soundscape (WAV)
  2. make_visuals.py renders one seamless visual loop (default 45 s)
  3. ffmpeg loops the visual to match the audio and muxes them (AAC 160k)

If you have your own footage instead of the generated scene, pass
--footage clip.mp4 and step 2 is skipped; the clip is looped instead.
"""
import argparse
import os
import subprocess
import sys

import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--theme", default="cyan")
    ap.add_argument("--loop-seconds", type=float, default=45)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--compressor", action="store_true")
    ap.add_argument("--footage", help="use this video clip as the visual loop instead of the generated scene")
    ap.add_argument("--workdir", default=os.path.join(HERE, "out"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    os.makedirs(args.workdir, exist_ok=True)
    tag = f"{args.theme}-{int(args.minutes)}m"
    out = args.out or os.path.join(args.workdir, f"garage-{tag}.mp4")
    wav = os.path.join(args.workdir, f"ambience-{int(args.minutes)}m.wav")
    loop = args.footage or os.path.join(args.workdir, f"loop-{args.theme}.mp4")

    amb = [sys.executable, os.path.join(HERE, "make_ambience.py"), "--minutes", str(args.minutes), "--out", wav]
    if args.compressor:
        amb.append("--compressor")
    run(amb)

    if not args.footage:
        run([sys.executable, os.path.join(HERE, "make_visuals.py"), "--seconds", str(args.loop_seconds),
             "--theme", args.theme, "--width", str(args.width), "--height", str(args.height), "--out", loop])

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    run([ffmpeg, "-y", "-stream_loop", "-1", "-i", loop, "-i", wav,
         "-map", "0:v:0", "-map", "1:a:0", "-shortest",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])
    print("\nDONE:", out)


if __name__ == "__main__":
    main()
