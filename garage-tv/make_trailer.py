#!/usr/bin/env python3
"""Make a 30-second vertical trailer (YouTube Short) for a PARKED FM video.

Two styles, so each video gets two different Shorts:
  card     (1080x1920) blurred photo fills the frame, the real photo sits in the middle with a
           slow push-in, PARKED FM / N HOURS on top, the scene title and a pointer to the full
           video below.
  closeup  the photo fills the whole tall frame, close on the car, drifting slowly across the
           room toward the window; a big hook line on top and the pointer to the full video.
Both open on the hook straight away (no slow fade from black). Audio comes from the album
where the music is playing (the closeup takes a later song), with soft fades.

  python3 make_trailer.py --image stills/x.webp --audio music.m4a --title "Supra in the Rain" --out trailer.mp4
"""
import argparse
import json
import math
import os
import subprocess
import sys
import textwrap

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import weekly  # noqa: E402  (shared lettering: word, brush_band, paste_shadowed, colours)
import statement  # noqa: E402  (the opening statement over the first seconds)

W, H, FPS = 1080, 1920, 30
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def cover(img, w, h):
    s = max(w / img.width, h / img.height)
    r = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--title", required=True, help="scene line, e.g. 'Supra in the Rain on a Mountain Road'")
    ap.add_argument("--label", default="CHILL LO-FI")
    ap.add_argument("--hours", type=int, default=8)
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--style", choices=["card", "closeup"], default="card")
    ap.add_argument("--hook", help="closeup: the big words on top; a newline splits the lines")
    ap.add_argument("--statement", help="a short line shown big over the first seconds")
    ap.add_argument("--out", default="trailer.mp4")
    args = ap.parse_args()

    photo = Image.open(args.image).convert("RGB")
    args._statement = statement.layer(args.statement, W, H) if args.statement else None
    if args.style == "closeup":
        return closeup(photo, args)

    # static layer: blurred, darkened background plus all the lettering
    bg = cover(photo, W, H).filter(ImageFilter.GaussianBlur(28))
    bg = ImageEnhance.Brightness(bg).enhance(0.45).convert("RGBA")
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    car_line = weekly.word(weekly.BRAND, 150, weekly.CREAM, distress=0.3, seed=3)
    sleep = weekly.word(weekly.TAGLINE, 46, weekly.AMBER, squeeze=0.95)
    car_line = car_line.resize((900, int(car_line.height * 900 / car_line.width)), Image.LANCZOS)
    if sleep.width > 860:
        sleep = sleep.resize((860, int(sleep.height * 860 / sleep.width)), Image.LANCZOS)
    y = 150
    weekly.paste_shadowed(top, car_line, ((W - car_line.width) // 2, y))
    y += car_line.height + 8
    weekly.paste_shadowed(top, sleep, ((W - sleep.width) // 2, y))
    y += sleep.height + 30
    band = weekly.brush_band(760, 130, 7)
    top.alpha_composite(band, ((W - band.width) // 2, y))
    hours = weekly.word(f"{args.hours} HOURS", 100, weekly.NAVY, squeeze=0.95)
    top.alpha_composite(hours, ((W - hours.width) // 2, y + (band.height - hours.height) // 2))

    photo_h = round(W * photo.height / photo.width)
    photo_y = 840
    d = ImageDraw.Draw(top)
    f_title = ImageFont.truetype(weekly.BOLD, 54)
    f_small = ImageFont.truetype(REG, 40)
    ty = photo_y + photo_h + 60
    for line in textwrap.wrap(args.title, 30):
        d.text((W // 2 + 3, ty + 3), line, font=f_title, fill=(0, 0, 0, 200), anchor="ma")
        d.text((W // 2, ty), line, font=f_title, fill=weekly.WHITE, anchor="ma")
        ty += 70
    d.text((W // 2, ty + 30), args.label, font=f_small, fill=weekly.ORANGE, anchor="ma")
    d.text((W // 2, H - 170), f"Full {args.hours}-hour video on the channel", font=f_small, fill=weekly.WHITE, anchor="ma")
    static = Image.alpha_composite(bg, Image.new("RGBA", (W, H), (0, 0, 0, 0)))

    n = int(args.seconds * FPS)
    proc = encoder(args, audio_start(args.audio, 0))
    for i in range(n):
        t = i / max(1, n - 1)
        z = 1.0 + 0.08 * t  # slow push-in over the whole trailer
        cw, ch = photo.width / z, photo.height / z
        ox, oy = (photo.width - cw) / 2, (photo.height - ch) / 2
        fg = photo.transform((W, photo_h), Image.AFFINE, (cw / W, 0, ox, 0, ch / photo_h, oy),
                             resample=Image.BICUBIC)
        frame = static.copy()
        frame.paste(fg, (0, photo_y))
        frame.alpha_composite(top)
        if args.statement:
            frame = statement.over(frame, args._statement, i / FPS)
        proc.stdin.write(faded(frame.convert("RGB"), i, n).tobytes())
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
           "-af", f"afade=t=in:d=0.6,afade=t=out:st={args.seconds - 2.5}:d=2.5",
           "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", args.out]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def faded(rgb, i, n):
    """Open on the picture almost at once (the first two seconds decide a scroll); fade out at the end."""
    alpha = min(1.0, i / (FPS * 0.2), (n - 1 - i) / (FPS * 1.5))
    return rgb if alpha >= 1 else Image.blend(Image.new("RGB", (W, H)), rgb, max(0.0, alpha))


def finish(proc, out):
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")
    print("wrote", out)


def closeup(photo, args):
    """The photo fills the tall frame, close on the car, drifting toward the window; a big hook on top."""
    # a tall window onto the photo: start over the car (left part), end nearer the window (right part)
    scale = H / photo.height * 1.12
    big_w = photo.width * scale
    x_from, x_to = 0.08 * big_w, min(big_w - W, 0.42 * big_w)
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shade = Image.new("L", (1, H))
    shade.putdata([int(170 * max(0.0, 1 - y / 620)) if y < 620 else int(150 * max(0.0, (y - H + 560) / 560))
                   for y in range(H)])
    top.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (W, H), 0)] * 3, shade.resize((W, H)))))
    brand = weekly.word(weekly.BRAND, 80, weekly.AMBER, squeeze=0.95)
    brand = brand.resize((440, int(brand.height * 440 / brand.width)), Image.LANCZOS)
    weekly.paste_shadowed(top, brand, ((W - brand.width) // 2, 120), blur=5, offset=2, strength=255)
    y = 120 + brand.height + 24
    hook = (args.hook or f"{args.hours} HOURS OF\n{args.label}").upper()
    for line in hook.split("\n") if "\n" in hook else textwrap.wrap(hook, 16):
        w = weekly.word(line, 120, weekly.CREAM, squeeze=0.9)
        if w.width > 980:
            w = w.resize((980, int(w.height * 980 / w.width)), Image.LANCZOS)
        weekly.paste_shadowed(top, w, ((W - w.width) // 2, y))
        y += w.height + 10
    d = ImageDraw.Draw(top)
    f_title = ImageFont.truetype(weekly.BOLD, 50)
    ty = H - 420
    for line in textwrap.wrap(args.title, 32):
        d.text((W // 2 + 3, ty + 3), line, font=f_title, fill=(0, 0, 0, 200), anchor="ma")
        d.text((W // 2, ty), line, font=f_title, fill=weekly.WHITE, anchor="ma")
        ty += 66
    band = weekly.brush_band(900, 110, 11)
    top.alpha_composite(band, ((W - band.width) // 2, H - 250))
    cta = weekly.word(f"FULL {args.hours}-HOUR VIDEO ON THE CHANNEL", 60, weekly.NAVY, squeeze=0.9)
    if cta.width > 820:
        cta = cta.resize((820, int(cta.height * 820 / cta.width)), Image.LANCZOS)
    top.alpha_composite(cta, ((W - cta.width) // 2, H - 250 + (band.height - cta.height) // 2))

    big = photo.resize((round(big_w), round(photo.height * scale)), Image.LANCZOS)
    yoff = (big.height - H) // 2
    n = int(args.seconds * FPS)
    proc = encoder(args, audio_start(args.audio, 1))
    for i in range(n):
        t = i / max(1, n - 1)
        ease = t * t * (3 - 2 * t)
        x = x_from + (x_to - x_from) * ease
        frame = big.crop((round(x), yoff, round(x) + W, yoff + H)).convert("RGBA")
        frame.alpha_composite(top)
        if args.statement:
            frame = statement.over(frame, args._statement, i / FPS)
        proc.stdin.write(faded(frame.convert("RGB"), i, n).tobytes())
    finish(proc, args.out)


if __name__ == "__main__":
    main()
