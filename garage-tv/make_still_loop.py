#!/usr/bin/env python3
"""Turn one photo into a seamless, slow-moving video loop (Ken Burns style).

The camera drifts and zooms on a closed path over --seconds, so the clip
loops with no visible seam. A faint drifting-dust layer and a very gentle
light "breathe" keep it from feeling like a frozen frame.

Usage:
  python3 make_still_loop.py --image stills/bay-dusk.webp --seconds 60 --out loop.mp4
"""
import argparse
import math
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import imageio_ffmpeg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--zoom", type=float, default=0.06, help="max extra zoom over the loop (0.06 = 6%%)")
    ap.add_argument("--drift", type=float, default=0.02, help="max sideways drift as a fraction of width")
    ap.add_argument("--dust", type=int, default=60, help="number of dust motes (0 to disable)")
    ap.add_argument("--out", default="loop.mp4")
    ap.add_argument("--seed", type=int, default=5)
    args = ap.parse_args()

    W, H = args.width, args.height
    rng = np.random.default_rng(args.seed)
    n_frames = int(args.seconds * args.fps)

    # Fit the source to the output aspect, then upscale with margin so the
    # crop window always stays inside the picture at maximum zoom + drift.
    src = Image.open(args.image).convert("RGB")
    margin = 1 + args.zoom + 2 * args.drift
    sw, sh = src.size
    scale = max(W * margin / sw, H * margin / sh)
    big = src.resize((int(sw * scale) + 1, int(sh * scale) + 1), Image.LANCZOS)
    big = big.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))
    BW, BH = big.size
    base = np.asarray(big, np.float32) / 255

    # dust motes: each one sways on a closed path (sine in x and y) so the
    # loop is exactly seamless, no wrap-around jump
    n_dust = args.dust
    px = rng.uniform(0, W, n_dust)
    py = rng.uniform(0, H, n_dust)
    ax = rng.uniform(15, 45, n_dust)          # sway amplitude, px
    ay = rng.uniform(8, 30, n_dust)
    kx = rng.integers(1, 3, n_dust)           # whole cycles per loop
    ky = rng.integers(1, 4, n_dust)
    phx = rng.uniform(0, 2 * math.pi, n_dust)
    phy = rng.uniform(0, 2 * math.pi, n_dust)
    pr = rng.uniform(0.7, 1.8, n_dust)
    pph = rng.uniform(0, 2 * math.pi, n_dust)

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y", "-f", "rawvideo", "-vcodec", "rawvideo", "-s", f"{W}x{H}",
        "-pix_fmt", "rgb24", "-r", str(args.fps), "-i", "-",
        # short keyframe interval + stillimage tune: every keyframe refresh is
        # invisible, so the loop seam (also a keyframe) is invisible too
        "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-tune", "stillimage",
        "-g", str(args.fps * 2), "-keyint_min", str(args.fps * 2), "-sc_threshold", "0",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    print(f"rendering {n_frames} frames at {W}x{H} from {args.image}...")
    for i in range(n_frames):
        t = i / n_frames
        # closed camera path: zoom breathes once per loop, drift traces a small ellipse
        z = 1 + args.zoom * (0.5 - 0.5 * math.cos(2 * math.pi * t))
        # crop window: at z=1 it shows the picture minus the margin, keeping the output aspect
        cw = int(min(BW, BW / margin / z))
        ch = int(cw * H / W)
        ox = (BW - cw) / 2 + args.drift * BW * 0.5 * math.sin(2 * math.pi * t)
        oy = (BH - ch) / 2 + args.drift * BH * 0.25 * math.sin(2 * math.pi * t + math.pi / 2)
        ox = int(round(max(0, min(BW - cw, ox))))
        oy = int(round(max(0, min(BH - ch, oy))))

        crop = big.crop((ox, oy, ox + cw, oy + ch)).resize((W, H), Image.BILINEAR)
        frame = np.asarray(crop, np.float32) / 255

        # very gentle light breathe (fluorescent tubes never sit perfectly still)
        frame *= 1 + 0.015 * math.sin(2 * math.pi * 3 * t)

        if n_dust:
            dust = Image.new("F", (W, H), 0.0)
            dd = ImageDraw.Draw(dust)
            for k in range(n_dust):
                x = px[k] + ax[k] * math.sin(2 * math.pi * kx[k] * t + phx[k])
                y = py[k] + ay[k] * math.sin(2 * math.pi * ky[k] * t + phy[k])
                tw = 0.5 + 0.5 * math.sin(2 * math.pi * 2 * t + pph[k])
                dd.ellipse([x - pr[k], y - pr[k], x + pr[k], y + pr[k]], fill=0.18 * tw)
            frame += np.asarray(dust, np.float32)[..., None]

        img = Image.fromarray((np.clip(frame, 0, 1) * 255).astype(np.uint8))
        proc.stdin.write(img.tobytes())
        if i % (args.fps * 10) == 0:
            print(f"  {i}/{n_frames}")

    proc.stdin.close()
    proc.wait()
    print("wrote", args.out)


if __name__ == "__main__":
    main()
