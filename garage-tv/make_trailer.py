#!/usr/bin/env python3
"""Make a ~15-second vertical Short for a PARKED FM video. Its sound is cut on whole bars and its end
blended into its start, so the Short loops without a seam (Mark's brief, Nov 1).

Two styles, so each video gets two Shorts that do different jobs:
  hook  (1080x1920) the car big from the very first frame, a slow push-in that comes back to where it
        started (so the Short loops seamlessly) and a soft light sweeping across the car; the day's
        statement glows at the top the whole time, the full-session pointer at the bottom.
  cuts  quick close shots of the car (the whole car, one end, the other end, the trading monitors, the car again)
        cut every 3 seconds with a slow push-in on each; a question on top, the pointer at the bottom.
Both are fully lit from frame 0 (the first frame is what people see before they swipe), and the car
is framed with a box Gemini finds in the picture (centre of the frame if that fails).

  python3 make_trailer.py --image stills/x.webp --audio music.m4a --title "Supra in the Night Studio" --out trailer.mp4
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import textwrap

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import weekly  # noqa: E402  (shared lettering: word, brush_band, paste_shadowed, colours)
import statement  # noqa: E402  (the glowing statement lettering)
import boxes  # noqa: E402  (where the car and monitors are, from Gemini)

W, H, FPS = 1080, 1920, 30
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FALLBACK_BOX = (0.22, 0.40, 0.78, 0.86)  # x0, y0, x1, y1: where the studio prompt usually puts the car


def cover(img, w, h):
    s = max(w / img.width, h / img.height)
    r = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def car_box(path):
    """(x0, y0, x1, y1) of the car as fractions of the picture (boxes.py), the usual spot if not found."""
    found = boxes.find(path, "car")
    return max(found, key=lambda b: (b[2] - b[0]) * (b[3] - b[1])) if found else FALLBACK_BOX


def view(photo, cx, cy, cw, ch, out_w, out_h):
    """The window (cx, cy centre; cw x ch size, in picture pixels) scaled to out_w x out_h."""
    cw, ch = min(cw, photo.width), min(ch, photo.height)
    ox = min(max(cx - cw / 2, 0), photo.width - cw)
    oy = min(max(cy - ch / 2, 0), photo.height - ch)
    return photo.transform((out_w, out_h), Image.AFFINE, (cw / out_w, 0, ox, 0, ch / out_h, oy),
                           resample=Image.BICUBIC)


def lettering(args, top_text):
    """The layer over the picture: soft shading top and bottom, brand, top text and the pointer."""
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shade = Image.new("L", (1, H))
    shade.putdata([int(150 * max(0.0, 1 - y / 700)) if y < 700 else int(150 * max(0.0, (y - H + 560) / 560))
                   for y in range(H)])
    top.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (W, H), 0)] * 3, shade.resize((W, H)))))
    brand = weekly.word(weekly.BRAND, 70, weekly.AMBER, squeeze=0.95)
    brand = brand.resize((360, int(brand.height * 360 / brand.width)), Image.LANCZOS)
    weekly.paste_shadowed(top, brand, ((W - brand.width) // 2, 110), blur=5, offset=2, strength=255)
    top.alpha_composite(statement.layer(top_text, W, H, center_y=400, size=88, wrap=18))
    d = ImageDraw.Draw(top)
    f_small = ImageFont.truetype(weekly.BOLD, 44)
    line = f"{args.hours} HOURS  ·  {args.label}"
    d.text((W // 2 + 2, H - 392), line, font=f_small, fill=(0, 0, 0, 200), anchor="ma")
    d.text((W // 2, H - 394), line, font=f_small, fill=weekly.CREAM, anchor="ma")
    # the brief's clean, crisp text box at the bottom
    f_cta = ImageFont.truetype(weekly.BOLD, 40)
    lines = ["The ultimate aesthetic to lock in your focus.", f"Full {args.hours}-hour session linked below \u2193"]
    box_h, box_y = 150, H - 300
    d.rounded_rectangle([60, box_y, W - 60, box_y + box_h], radius=22, fill=(10, 12, 18, 200),
                        outline=(*weekly.AMBER, 255), width=3)
    for k, line in enumerate(lines):
        d.text((W // 2, box_y + 28 + k * 54), line, font=f_cta, fill=(255, 255, 255, 255), anchor="ma")
    return top


def sweep(frame, t, x0, x1, y0, y1):
    """A soft band of light passing across the car once (t from 0 to 1), gone at both ends; it only
    brightens what is already lit, so it reads as a reflection rather than a stripe."""
    pos = -0.3 + 1.6 * t
    if not 0 < pos < 1:
        return frame
    xs = np.arange(W)[None, :]
    ys = np.arange(H)[:, None]
    centre = x0 + (x1 - x0) * pos + (ys - (y0 + y1) / 2) * 0.35  # leaning band
    mid, half = (y0 + y1) / 2, (y1 - y0) / 2
    a = np.exp(-((xs - centre) / 70.0) ** 2) * np.exp(-((ys - mid) / half) ** 4)
    arr = np.asarray(frame.convert("RGB"), np.float32)
    lit = arr.mean(axis=2, keepdims=True) / 255
    arr = arr + (a[..., None] * 160 * np.clip(lit * 1.6, 0, 1))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--title", required=True, help="scene line, e.g. 'Supra in the Night Studio'")
    ap.add_argument("--label", default="LO-FI BEATS")
    ap.add_argument("--hours", type=int, default=2)
    ap.add_argument("--seconds", type=float, default=15)
    ap.add_argument("--style", choices=["hook", "cuts"], default="hook")
    ap.add_argument("--hook", help="the words on top (hook style: the statement; cuts style: a question)")
    ap.add_argument("--statement", help="the day's statement; the hook style shows it on top")
    ap.add_argument("--grade", default="none", help="colour grade, as in the video (make_still_loop.GRADES)")
    ap.add_argument("--out", default="trailer.mp4")
    args = ap.parse_args()

    from make_still_loop import grade
    photo = grade(Image.open(args.image).convert("RGB"), args.grade)
    bx0, by0, bx1, by1 = car_box(args.image)
    pw, ph = photo.size
    car = dict(cx=(bx0 + bx1) / 2 * pw, cy=(by0 + by1) / 2 * ph, w=(bx1 - bx0) * pw, h=(by1 - by0) * ph,
               x0=bx0 * pw, x1=bx1 * pw)
    args.loop_wav, args.seconds = loop_audio(args.audio, audio_start(args.audio, 1 if args.style == "cuts" else 0),
                                             args.seconds)
    if args.style == "cuts":
        return cuts(photo, car, args)

    top = lettering(args, args.statement or args.hook or "Lock in.")
    # the car fills most of the width: a window 1.15x the car's width, as tall as the picture allows
    cw = max(car["w"] * 1.15, ph * 9 / 16 * 0.6)
    ch = min(ph, cw * H / W)
    band_h = round(W * ch / cw)  # shorter than the frame when the picture isn't tall enough
    band_y = max(0, min(H - band_h, 1060 - band_h // 2))
    bg = ImageEnhance.Brightness(cover(photo, W, H).filter(ImageFilter.GaussianBlur(30))).enhance(0.5)
    n = int(args.seconds * FPS)
    proc = encoder(args)
    for i in range(n):
        t = i / n
        z = 1 + 0.07 * (0.5 - 0.5 * math.cos(2 * math.pi * t))  # in and back out: loops seamlessly
        dx = 0.04 * car["w"] * math.sin(2 * math.pi * t)
        fg = view(photo, car["cx"] + dx, car["cy"] - ch * 0.05, cw / z, ch / z, W, band_h)
        frame = bg.copy()
        frame.paste(fg, (0, band_y))
        sx0 = (W - W / 1.15) / 2
        frame = sweep(frame, t, sx0, W - sx0, band_y + band_h * 0.3, band_y + band_h * 0.8).convert("RGBA")
        frame.alpha_composite(top)
        proc.stdin.write(frame.convert("RGB").tobytes())
    finish(proc, args.out)


def cuts(photo, car, args):
    """Close shots of the car cut every 3 seconds, each with a slow push-in."""
    pw, ph = photo.size
    top = lettering(args, args.hook or "Would you work in here?")
    tall = lambda h: (h * W / H, h)  # noqa: E731  a 9:16 window of height h
    shots = [  # (centre x, centre y, window w, window h)
        (car["cx"], car["cy"], *tall(min(ph, max(car["h"] * 2.6, car["w"] * 1.25 * H / W)))),
        (car["x0"] + car["w"] * 0.25, car["cy"], *tall(min(ph, car["h"] * 1.7))),
        (car["x0"] + car["w"] * 0.75, car["cy"], *tall(min(ph, car["h"] * 1.7))),
        (pw / 2, ph / 2, *tall(ph)),
        (car["cx"], car["cy"], *tall(min(ph, car["h"] * 2.1))),
    ]
    screens = boxes.find(args.image, "monitors")
    if screens:  # the brief's shot: tight on the glowing trading monitors and the desk
        mx0, my0 = min(b[0] for b in screens) * pw, min(b[1] for b in screens) * ph
        mx1, my1 = max(b[2] for b in screens) * pw, max(b[3] for b in screens) * ph
        shots[3] = ((mx0 + mx1) / 2, (my0 + my1) / 2 + (my1 - my0) * 0.6,
                    *tall(min(ph, max((my1 - my0) * 3.2, (mx1 - mx0) * 1.15 * H / W))))
    per = int(3 * FPS)
    n = int(args.seconds * FPS)
    proc = encoder(args)
    for i in range(n):
        cx, cy, cw, ch = shots[min(i // per, len(shots) - 1)]
        z = 1 + 0.08 * (i % per) / per
        frame = view(photo, cx, cy, cw / z, ch / z, W, H).convert("RGBA")
        frame.alpha_composite(top)
        proc.stdin.write(frame.convert("RGB").tobytes())
    finish(proc, args.out)


def audio_start(audio, song):
    """Where in the album to take the Short's sound: past the intro of song number `song`."""
    tracks = os.path.splitext(audio)[0] + ".tracks.json"
    if os.path.exists(tracks):
        st = json.load(open(tracks)).get("track_starts") or []
        if st:
            return st[min(song, len(st) - 1)] + 40  # past the intro, into the groove
    return 0.0


def loop_audio(audio, start, target):
    """A stretch of the music that loops without a seam: its length is a whole number of bars (beat
    found from the music itself) near `target` seconds, and its last half second is blended into the
    first, so when YouTube or TikTok replays the Short you can't hear where it starts.
    Returns (wav path, seconds)."""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    sr = 44100
    raw = subprocess.run([ff, "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{target * 2 + 4:.2f}", "-i", audio,
                          "-f", "f32le", "-ac", "2", "-ar", str(sr), "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
    hop = 512
    mono = x.mean(axis=1)
    energy = np.sqrt(np.convolve(mono ** 2, np.ones(hop) / hop, "same")[::hop])
    onset = np.maximum(0, np.diff(energy))
    onset -= onset.mean()
    fps = sr / hop
    lags = np.arange(int(fps * 60 / 180), int(fps * 60 / 60) + 1)  # 60-180 BPM
    ac = [float(np.dot(onset[:-lag], onset[lag:])) for lag in lags]
    beat = lags[int(np.argmax(ac))] / fps if len(onset) > lags[-1] * 2 else 60 / 80
    bar = 4 * beat
    seconds = bar * max(1, round(target / bar))
    while seconds > 30:
        seconds -= bar
    while seconds < 10:
        seconds += bar
    n, xf = int(seconds * sr), int(0.5 * sr)
    if len(x) < n + xf:
        n = len(x) - xf
        seconds = n / sr
    out = x[:n].copy()
    ramp = np.sin(np.linspace(0, np.pi / 2, xf))[:, None]  # equal-power blend of the tail into the head
    out[:xf] = x[:xf] * ramp + x[n:n + xf] * np.cos(np.linspace(0, np.pi / 2, xf))[:, None]
    path = tempfile.mktemp(suffix=".wav")
    subprocess.run([ff, "-loglevel", "error", "-y", "-f", "f32le", "-ac", "2", "-ar", str(sr), "-i", "-",
                    "-c:a", "pcm_s16le", path], input=out.astype(np.float32).tobytes(), check=True)
    print(f"seamless sound: beat {60 / beat:.0f} BPM, {seconds:.2f} s ({round(seconds / bar)} bars)")
    return path, seconds


def encoder(args):
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", args.loop_wav, "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", args.out]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def finish(proc, out):
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")
    print("wrote", out)


if __name__ == "__main__":
    main()
