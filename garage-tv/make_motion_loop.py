#!/usr/bin/env python3
"""Turn a short moving clip (e.g. a 12 s Sora video) into a seamless 1440p loop.

The last --blend seconds of the clip are cross-faded into its first seconds, so the loop's
last frame runs straight into its first: a 12 s clip becomes a 10.5 s loop with no jump.
Ask for a locked-off camera in the clip; a moving camera can't blend cleanly.

  python3 make_motion_loop.py --clip sora.mp4 --out loop.mp4
"""
import argparse
import subprocess
import sys

import imageio_ffmpeg

FPS = 30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--blend", type=float, default=1.5, help="seconds of cross-fade at the seam")
    ap.add_argument("--crf", type=int, default=20)
    args = ap.parse_args()

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    frames, secs = imageio_ffmpeg.count_frames_and_secs(args.clip)
    n = int(secs * FPS)  # frames at our frame rate
    x = int(args.blend * FPS)
    if n < 3 * x:
        sys.exit(f"clip too short to loop: {secs:.1f} s")
    tail0 = (n - x) / FPS
    vf = (f"[0:v]fps={FPS},scale=2560:1440:flags=lanczos,setsar=1,format=yuv420p,split[a][b];"
          f"[a]trim=start={tail0}:end={n / FPS},setpts=PTS-STARTPTS,fps={FPS}[t];"
          f"[b]trim=start=0:end={tail0},setpts=PTS-STARTPTS,fps={FPS}[h];"
          f"[t][h]xfade=transition=fade:duration={args.blend}:offset=0,format=yuv420p[v]")
    cmd = [ff, "-y", "-loglevel", "error", "-i", args.clip, "-filter_complex", vf, "-map", "[v]", "-an",
           "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf), "-pix_fmt", "yuv420p",
           "-x264-params", f"keyint={n - x}:min-keyint={n - x}:scenecut=0", "-movflags", "+faststart", args.out]
    subprocess.run(cmd, check=True)
    print(f"wrote {args.out} ({(n - x) / FPS:.1f} s seamless loop from a {secs:.1f} s clip)")


if __name__ == "__main__":
    main()
