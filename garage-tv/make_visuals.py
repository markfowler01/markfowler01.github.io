#!/usr/bin/env python3
"""Render a seamless, slow-moving 'car in a dark garage' visual loop.

Everything in the scene is periodic over --seconds, so the clip can be
looped forever with ffmpeg's -stream_loop without a visible seam.

Scene: dark shop, a coupe silhouette under a neon strip, a soft light that
slowly sweeps across the body, a floor reflection, drifting dust, and a very
slow breathing zoom. Colour themes: cyan | amber | red | purple | white.

Usage:
  python3 make_visuals.py --seconds 45 --theme cyan --out loop.mp4
"""
import argparse
import math
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import imageio_ffmpeg

THEMES = {
    "cyan":   (70, 220, 255),
    "amber":  (255, 170, 60),
    "red":    (255, 70, 80),
    "purple": (180, 90, 255),
    "white":  (235, 235, 245),
}

# Coupe side profile, unit coords (x 0..1 left->right, y 0..1 top->bottom)
BODY = [
    (0.00, 0.62), (0.02, 0.55), (0.06, 0.52), (0.28, 0.47), (0.33, 0.44),
    (0.42, 0.30), (0.47, 0.27), (0.62, 0.26), (0.70, 0.29), (0.80, 0.38),
    (0.94, 0.45), (0.99, 0.50), (1.00, 0.62), (0.99, 0.72), (0.90, 0.74),
    (0.88, 0.70), (0.72, 0.70), (0.70, 0.74), (0.30, 0.74), (0.28, 0.70),
    (0.12, 0.70), (0.10, 0.74), (0.01, 0.72),
]
GLASS = [
    (0.36, 0.45), (0.44, 0.32), (0.48, 0.30), (0.61, 0.29), (0.68, 0.32),
    (0.76, 0.40), (0.60, 0.43),
]
WHEELS = [(0.20, 0.72, 0.105), (0.80, 0.72, 0.105)]


def poly(points, ox, oy, w, h):
    return [(ox + x * w, oy + y * h) for x, y in points]


def render_base(W, H, theme, car_w):
    """Static layers: background, floor, car body, glass, wheels, reflection."""
    rgb = np.array(theme, dtype=np.float32) / 255.0

    # background gradient: near-black top, dark concrete floor
    yy = np.linspace(0, 1, H)[:, None]
    bg = np.zeros((H, W, 3), np.float32)
    horizon = 0.62
    wall = 0.035 + 0.02 * yy / horizon
    floor = 0.09 + 0.04 * (yy - horizon) / (1 - horizon)
    bg[:] = np.where(yy < horizon, wall, floor)[..., None]
    # slight tint from the neon on the wall
    bg += 0.05 * rgb * np.clip(1 - yy / horizon, 0, 1)[..., None]

    # car
    car_h = car_w * 0.40
    ox = (W - car_w) / 2
    oy = H * horizon - car_h * (WHEELS[0][1] + WHEELS[0][2])  # tires touch the floor line
    body_img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(body_img)
    d.polygon(poly(BODY, ox, oy, car_w, car_h), fill=255)
    glass_img = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glass_img).polygon(poly(GLASS, ox, oy, car_w, car_h), fill=255)
    wheel_img = Image.new("L", (W, H), 0)
    rim_img = Image.new("L", (W, H), 0)
    for cx, cy, r in WHEELS:
        x, y, rr = ox + cx * car_w, oy + cy * car_h, r * car_h
        ImageDraw.Draw(wheel_img).ellipse([x - rr, y - rr, x + rr, y + rr], fill=255)
        ImageDraw.Draw(rim_img).ellipse([x - rr * 0.55, y - rr * 0.55, x + rr * 0.55, y + rr * 0.55], fill=255)

    body = np.asarray(body_img, np.float32) / 255
    glass = np.asarray(glass_img, np.float32) / 255
    wheel = np.asarray(wheel_img, np.float32) / 255
    rim = np.asarray(rim_img, np.float32) / 255

    # body shading: gradient top-lit, slight tint of neon on the roof
    car_shade = 0.10 + 0.12 * np.clip(1 - (np.arange(H)[:, None] - oy) / car_h, 0, 1)
    car_col = np.stack([car_shade] * 3, -1) * (0.6 + 0.4 * rgb)
    scene = bg * (1 - body[..., None]) + car_col * body[..., None]
    scene = scene * (1 - glass[..., None]) + (0.05 + 0.25 * rgb) * glass[..., None] * 0.9 + scene * glass[..., None] * 0.1
    scene = scene * (1 - wheel[..., None]) + 0.03 * wheel[..., None]
    scene = scene * (1 - rim[..., None]) + 0.30 * rim[..., None]

    # rim light: edge of the body glows faintly with the neon colour
    edge = body_img.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1.5))
    edge = np.asarray(edge, np.float32) / 255
    scene += 0.9 * rgb * edge[..., None]

    # floor reflection (flipped car, faded, blurred)
    car_only = (scene * body[..., None]).copy()
    floor_y = int(H * horizon)
    refl = np.flipud(car_only[:floor_y])
    refl_mask = np.flipud(body[:floor_y])
    fade = np.exp(-np.arange(refl.shape[0]) / (car_h * 0.35))[:, None, None]
    r_img = Image.fromarray((np.clip(refl, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
    refl = np.asarray(r_img, np.float32) / 255 * fade * 0.6
    m = (refl_mask * fade[..., 0])[..., None]
    rows = min(refl.shape[0], H - floor_y)
    refl, m = refl[:rows], m[:rows]
    region = scene[floor_y:floor_y + rows]
    scene[floor_y:floor_y + rows] = region * (1 - m) + refl * m + region * m * 0.5

    # vignette
    xx = np.linspace(-1, 1, W)[None, :]
    yv = np.linspace(-1, 1, H)[:, None]
    vig = 1 - 0.55 * np.clip((xx ** 2 + yv ** 2) - 0.25, 0, 1)
    scene *= vig[..., None]

    return scene, body, ox, oy, car_w, car_h, floor_y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=45)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--theme", choices=THEMES, default="cyan")
    ap.add_argument("--out", default="loop.mp4")
    ap.add_argument("--seed", type=int, default=3)
    args = ap.parse_args()

    W, H = args.width, args.height
    theme = THEMES[args.theme]
    rgb = np.array(theme, np.float32) / 255
    rng = np.random.default_rng(args.seed)
    n_frames = int(args.seconds * args.fps)

    base, body, ox, oy, car_w, car_h, floor_y = render_base(W, H, theme, car_w=W * 0.62)

    # neon strip glow (static shape, animated brightness)
    neon = Image.new("L", (W, H), 0)
    ImageDraw.Draw(neon).rectangle([W * 0.12, H * 0.13, W * 0.88, H * 0.135], fill=255)
    neon_glow = np.asarray(neon.filter(ImageFilter.GaussianBlur(28)), np.float32) / 255
    neon_core = np.asarray(neon.filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255

    # dust particles: each sways on a closed sine path so the loop is exactly seamless
    n_dust = 90
    px = rng.uniform(0, W, n_dust)
    py = rng.uniform(H * 0.1, H * 0.95, n_dust)
    ax = rng.uniform(15, 45, n_dust)
    ay = rng.uniform(8, 30, n_dust)
    kx = rng.integers(1, 3, n_dust)
    ky = rng.integers(1, 4, n_dust)
    phx = rng.uniform(0, 2 * math.pi, n_dust)
    phy = rng.uniform(0, 2 * math.pi, n_dust)
    pr = rng.uniform(0.8, 2.2, n_dust)
    pph = rng.uniform(0, 2 * math.pi, n_dust)

    # render with a margin so the slow zoom never shows the edge
    zoom_amp = 0.03
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y", "-f", "rawvideo", "-vcodec", "rawvideo", "-s", f"{W}x{H}",
        "-pix_fmt", "rgb24", "-r", str(args.fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-tune", "stillimage",
        "-g", str(args.fps * 2), "-keyint_min", str(args.fps * 2), "-sc_threshold", "0",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    xs = np.arange(W)[None, :]
    ys = np.arange(H)[:, None]
    print(f"rendering {n_frames} frames at {W}x{H}...")
    for i in range(n_frames):
        t = i / n_frames  # 0..1 over the loop
        frame = base.copy()

        # sweeping soft light across the car body, one full sweep per loop
        sx = ox + car_w * (0.5 + 0.55 * math.sin(2 * math.pi * t))
        sweep = np.exp(-((xs - sx) ** 2) / (2 * (car_w * 0.12) ** 2)).astype(np.float32)
        sweep = sweep * np.clip(1 - (ys - oy) / (car_h * 1.6), 0, 1)
        frame += 0.35 * sweep[..., None] * (0.7 + 0.3 * rgb) * body[..., None]
        # and a faint pool of that light on the floor
        frame += 0.05 * sweep[..., None] * (ys >= floor_y)[..., None]

        # neon breathing
        pulse = 0.85 + 0.15 * math.sin(2 * math.pi * 2 * t)
        frame += pulse * (0.55 * neon_glow[..., None] * rgb + 0.9 * neon_core[..., None] * (0.5 + 0.5 * rgb))

        # dust
        dust = Image.new("F", (W, H), 0.0)
        dd = ImageDraw.Draw(dust)
        for k in range(n_dust):
            x = px[k] + ax[k] * math.sin(2 * math.pi * kx[k] * t + phx[k])
            y = py[k] + ay[k] * math.sin(2 * math.pi * ky[k] * t + phy[k])
            tw = 0.5 + 0.5 * math.sin(2 * math.pi * 3 * t + pph[k])
            dd.ellipse([x - pr[k], y - pr[k], x + pr[k], y + pr[k]], fill=0.25 * tw)
        frame += np.asarray(dust, np.float32)[..., None] * (0.6 + 0.4 * rgb)

        # slow breathing zoom, periodic over the loop
        z = 1 + zoom_amp * (0.5 - 0.5 * math.cos(2 * math.pi * t))
        cw, ch = int(W / z), int(H / z)
        x0, y0 = (W - cw) // 2, (H - ch) // 2
        crop = np.clip(frame[y0:y0 + ch, x0:x0 + cw], 0, 1)
        img = Image.fromarray((crop * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
        proc.stdin.write(img.tobytes())
        if i % (args.fps * 5) == 0:
            print(f"  {i}/{n_frames}")

    proc.stdin.close()
    proc.wait()
    print("wrote", args.out)


if __name__ == "__main__":
    main()
