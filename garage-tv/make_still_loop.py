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


# Colour grades: (brightness, R, G, B multipliers). Keep them subtle; the photo does the work.
GRADES = {
    "none":  (1.00, 1.00, 1.00, 1.00),
    "night": (0.78, 0.86, 0.93, 1.10),   # later, bluer, darker
    "amber": (0.95, 1.08, 1.00, 0.84),   # warm work-light glow
    "cold":  (0.88, 0.92, 0.98, 1.06),   # winter night
    "bright": (1.06, 1.00, 1.00, 1.00),  # lifts the shadows (see grade) for the dark night-studio pictures
}


def grade(img, name):
    b, r, g, bl = GRADES[name]
    if name == "none":
        return img
    a = np.asarray(img, np.float32) / 255
    if name == "bright":
        a = a ** 0.78  # gamma: opens up the shadows much more than the highlights
    a = a * b * np.array([r, g, bl], np.float32)
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--zoom", type=float, default=0.06, help="max extra zoom over the loop (0.06 = 6%%)")
    ap.add_argument("--drift", type=float, default=0.02, help="max sideways drift as a fraction of width")
    ap.add_argument("--dust", type=int, default=60, help="number of dust motes (0 to disable)")
    ap.add_argument("--rain", type=int, default=0, help="number of falling rain streaks (0 = no rain; ~700 is a steady rain)")
    ap.add_argument("--rain-angle", type=float, default=8, help="rain slant in degrees")
    ap.add_argument("--grade", choices=GRADES, default="none", help="colour grade applied to the photo")
    ap.add_argument("--crf", type=int, default=22, help="x264 quality (higher = smaller file; above ~24 slow motion starts to stutter)")
    ap.add_argument("--monitors", action="store_true",
                    help="make the glow of the picture's monitors pulse slowly, like live charts (Gemini finds them)")
    ap.add_argument("--out", default="loop.mp4")
    ap.add_argument("--seed", type=int, default=5)
    args = ap.parse_args()

    W, H = args.width, args.height
    rng = np.random.default_rng(args.seed)
    n_frames = int(args.seconds * args.fps)

    # Fit the source to the output aspect, then upscale with margin so the
    # crop window always stays inside the picture at maximum zoom + drift.
    src = grade(Image.open(args.image).convert("RGB"), args.grade)
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

    # falling rain streaks in three depth layers. Each streak falls a whole number
    # of screen-heights per loop, so frame 0 and the frame after the last match exactly.
    rain = []
    if args.rain:
        slant = math.tan(math.radians(args.rain_angle))
        layers = [  # share of streaks, seconds to cross the screen, streak length px, width, brightness
            (0.55, 0.95, (18, 34), 1, 0.06),
            (0.32, 0.55, (40, 70), 1, 0.10),
            (0.13, 0.32, (80, 130), 2, 0.13),
        ]
        for share, cross, (lmin, lmax), width, bright in layers:
            m = int(args.rain * share)
            length = rng.uniform(lmin, lmax, m)
            span = H + length
            k = np.maximum(1, np.round(args.seconds / (cross * rng.uniform(0.85, 1.15, m))))
            rain.append(dict(x0=rng.uniform(-0.2 * W, 1.1 * W, m), y0=rng.uniform(0, 1, m) * span,
                             k=k, length=length, span=span, width=width,
                             bright=bright * rng.uniform(0.6, 1.0, m), slant=slant))
    rain_tint = np.array([0.82, 0.88, 1.0], np.float32)

    # glowing monitors (boxes.py): a soft-edged mask per screen in the big picture's coordinates; each
    # pulses a little brighter and back, a whole number of times per loop so the loop stays seamless
    screens = []
    if args.monitors:
        import boxes
        for k, (x0, y0, x1, y1) in enumerate(boxes.find(args.image, "monitors")[:4]):
            m = Image.new("L", (BW, BH), 0)
            pad = 0.15 * (x1 - x0) * BW
            ImageDraw.Draw(m).rectangle([x0 * BW - pad, y0 * BH - pad, x1 * BW + pad, y1 * BH + pad], fill=255)
            screens.append((m.filter(ImageFilter.GaussianBlur(pad * 0.8)), rng.uniform(0, 2 * math.pi), 6 + 2 * k))

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y", "-f", "rawvideo", "-vcodec", "rawvideo", "-s", f"{W}x{H}",
        "-pix_fmt", "rgb24", "-r", str(args.fps), "-i", "-",
        # no-fast-pskip: x264 normally "skips" blocks that barely changed, which freezes a
        # slow camera drift until it jumps; turning that off keeps slow motion smooth.
        # aq-mode 3 keeps dark gradients from banding. A keyframe every 10 s (the loop
        # seam is one of them) at this quality refreshes invisibly.
        "-an", "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf),
        "-x264-params", "no-fast-pskip=1:aq-mode=3",
        "-g", str(args.fps * 10), "-keyint_min", str(args.fps * 10), "-sc_threshold", "0",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    print(f"rendering {n_frames} frames at {W}x{H} from {args.image}...")
    for i in range(n_frames):
        t = i / n_frames
        # closed camera path: zoom breathes once per loop, drift traces a small ellipse
        z = 1 + args.zoom * (0.5 - 0.5 * math.cos(2 * math.pi * t))
        # crop window: at z=1 it shows the picture minus the margin, keeping the output aspect.
        # Everything stays in fractional pixels: rounding the window to whole pixels made the
        # slow drift sit still for several frames and then jump, which reads as choppy.
        # the biggest window of the output's shape that fits the picture (a picture wider than 16:9
        # is limited by its height; sizing by width alone ran off the bottom and left a black band)
        cw = min(BW, BH * W / H) / margin / z
        ch = cw * H / W
        ox = (BW - cw) / 2 + args.drift * BW * 0.5 * math.sin(2 * math.pi * t)
        oy = (BH - ch) / 2 + args.drift * BH * 0.25 * math.sin(2 * math.pi * t + math.pi / 2)
        ox = max(0.0, min(BW - cw, ox))
        oy = max(0.0, min(BH - ch, oy))

        crop = big.transform((W, H), Image.AFFINE, (cw / W, 0, ox, 0, ch / H, oy), resample=Image.BICUBIC)
        frame = np.asarray(crop, np.float32) / 255

        # very gentle light breathe (fluorescent tubes never sit perfectly still)
        frame *= 1 + 0.015 * math.sin(2 * math.pi * 3 * t)
        for mask, phase, cycles in screens:
            m = np.asarray(mask.transform((W, H), Image.AFFINE, (cw / W, 0, ox, 0, ch / H, oy),
                                          resample=Image.BILINEAR), np.float32) / 255
            frame *= 1 + 0.14 * math.sin(2 * math.pi * cycles * t + phase) * m[..., None]

        if n_dust:
            # each mote is a soft dot drawn at its exact fractional position, so it glides
            # instead of hopping pixel to pixel
            dust = np.zeros((H, W), np.float32)
            for k in range(n_dust):
                x = px[k] + ax[k] * math.sin(2 * math.pi * kx[k] * t + phx[k])
                y = py[k] + ay[k] * math.sin(2 * math.pi * ky[k] * t + phy[k])
                tw = 0.5 + 0.5 * math.sin(2 * math.pi * 2 * t + pph[k])
                x0, x1 = max(0, int(x) - 4), min(W, int(x) + 5)
                y0, y1 = max(0, int(y) - 4), min(H, int(y) + 5)
                if x0 >= x1 or y0 >= y1:
                    continue
                gx = np.arange(x0, x1, dtype=np.float32) - x
                gy = np.arange(y0, y1, dtype=np.float32)[:, None] - y
                s = 0.55 * pr[k]
                dust[y0:y1, x0:x1] += 0.2 * tw * np.exp(-(gx ** 2 + gy ** 2) / (2 * s * s))
            frame += dust[..., None]

        if rain:
            sheet = Image.new("L", (W, H), 0)
            sd = ImageDraw.Draw(sheet)
            for L in rain:
                ys = (L["y0"] + L["k"] * L["span"] * t) % L["span"] - L["length"]  # top of each streak
                for x0, y, ln, b in zip(L["x0"], ys, L["length"], L["bright"]):
                    xa = x0 + L["slant"] * y
                    sd.line([(xa, y), (xa + L["slant"] * ln, y + ln)], fill=int(b * 255), width=L["width"])
            sheet = sheet.filter(ImageFilter.GaussianBlur(0.8))
            frame += (np.asarray(sheet, np.float32) / 255)[..., None] * rain_tint

        img = Image.fromarray((np.clip(frame, 0, 1) * 255).astype(np.uint8))
        proc.stdin.write(img.tobytes())
        if i % (args.fps * 10) == 0:
            print(f"  {i}/{n_frames}")

    proc.stdin.close()
    proc.wait()
    print("wrote", args.out)


if __name__ == "__main__":
    main()
