#!/usr/bin/env python3
"""Make a 15-second vertical Short for a PARKED FM video.

Two styles, so each video gets two Shorts that do different jobs:
  hook  (1080x1920) the car big from the very first frame, a slow push-in that comes back to where it
        started (so the Short loops seamlessly) and a soft light sweeping across the car; the day's
        statement glows at the top the whole time, the full-session pointer at the bottom.
  cuts  quick close shots of the car (the whole car, one end, the other end, the room, the car again)
        cut every 3 seconds with a slow push-in on each; a question on top, the pointer at the bottom.
Both are fully lit from frame 0 (the first frame is what people see before they swipe), and the car
is framed with a box Gemini finds in the picture (centre of the frame if that fails).

  python3 make_trailer.py --image stills/x.webp --audio music.m4a --title "Supra in the Night Studio" --out trailer.mp4
"""
import argparse
import base64
import hashlib
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import weekly  # noqa: E402  (shared lettering: word, brush_band, paste_shadowed, colours)
import statement  # noqa: E402  (the glowing statement lettering)

W, H, FPS = 1080, 1920, 30
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FALLBACK_BOX = (0.22, 0.40, 0.78, 0.86)  # x0, y0, x1, y1: where the studio prompt usually puts the car


def cover(img, w, h):
    s = max(w / img.width, h / img.height)
    r = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def car_box(photo, path):
    """(x0, y0, x1, y1) of the car as fractions of the picture, from Gemini; cached per picture."""
    cache = os.path.join(tempfile.gettempdir(), "carbox-" + hashlib.md5(open(path, "rb").read()).hexdigest() + ".json")
    if os.path.exists(cache):
        return tuple(json.load(open(cache)))
    box = FALLBACK_BOX
    if os.environ.get("GEMINI_API_KEY"):
        try:
            small = photo.copy()
            small.thumbnail((1024, 1024))
            buf = io.BytesIO()
            small.save(buf, "JPEG", quality=85)
            body = {"contents": [{"parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}},
                {"text": "Find the main car in this picture. Reply with JSON only: "
                         '{"box_2d": [ymin, xmin, ymax, xmax]} on a 0-1000 scale, tight around the whole car.'}]}]}
            model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-latest")
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                data=json.dumps(body).encode(), method="POST")
            req.add_header("x-goog-api-key", os.environ["GEMINI_API_KEY"])
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=90) as r:
                text = "".join(p.get("text", "") for p in json.load(r)["candidates"][0]["content"]["parts"])
            y0, x0, y1, x1 = [v / 1000 for v in json.loads(re.search(r"\{.*?\}", text, re.S).group(0))["box_2d"]]
            if 0.03 < (x1 - x0) * (y1 - y0) < 0.9 and x1 > x0 and y1 > y0:
                box = (x0, y0, x1, y1)
            print("car box from Gemini:", [round(v, 3) for v in box])
        except Exception as e:  # any failure: frame the usual spot
            print("car box: using the default spot", repr(e)[:160])
    json.dump(box, open(cache, "w"))
    return box


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
    d.text((W // 2 + 2, H - 372), line, font=f_small, fill=(0, 0, 0, 200), anchor="ma")
    d.text((W // 2, H - 374), line, font=f_small, fill=weekly.CREAM, anchor="ma")
    band = weekly.brush_band(900, 110, 11)
    top.alpha_composite(band, ((W - band.width) // 2, H - 280))
    cta = weekly.word("FULL SESSION ON THE CHANNEL", 60, weekly.NAVY, squeeze=0.9)
    if cta.width > 820:
        cta = cta.resize((820, int(cta.height * 820 / cta.width)), Image.LANCZOS)
    top.alpha_composite(cta, ((W - cta.width) // 2, H - 280 + (band.height - cta.height) // 2))
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
    bx0, by0, bx1, by1 = car_box(photo, args.image)
    pw, ph = photo.size
    car = dict(cx=(bx0 + bx1) / 2 * pw, cy=(by0 + by1) / 2 * ph, w=(bx1 - bx0) * pw, h=(by1 - by0) * ph,
               x0=bx0 * pw, x1=bx1 * pw)
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
    proc = encoder(args, audio_start(args.audio, 0))
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
    per = int(3 * FPS)
    n = int(args.seconds * FPS)
    proc = encoder(args, audio_start(args.audio, 1))
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


def encoder(args, start):
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-ss", f"{start:.2f}", "-t", str(args.seconds), "-i", args.audio,
           "-map", "0:v", "-map", "1:a",
           "-af", f"afade=t=in:d=0.15,afade=t=out:st={args.seconds - 1.5}:d=1.5",
           "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", args.out]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def finish(proc, out):
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")
    print("wrote", out)


if __name__ == "__main__":
    main()
