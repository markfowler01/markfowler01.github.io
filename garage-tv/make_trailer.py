#!/usr/bin/env python3
"""Make a 30-second vertical trailer (YouTube Short) for a Car People Sleep video.

Layout (1080x1920): blurred photo fills the frame, the real photo sits in the middle with a
slow push-in, Car People Sleep / 8 HOURS on top, the scene title and a pointer to the full
video below. Audio is taken from the album where the music is playing, with soft fades.

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
    ap.add_argument("--label", default="WHITE NOISE + LO-FI")
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--out", default="trailer.mp4")
    args = ap.parse_args()

    photo = Image.open(args.image).convert("RGB")

    # static layer: blurred, darkened background plus all the lettering
    bg = cover(photo, W, H).filter(ImageFilter.GaussianBlur(28))
    bg = ImageEnhance.Brightness(bg).enhance(0.45).convert("RGBA")
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    car_line = weekly.word(weekly.BRAND_LINES[0], 150, weekly.WHITE, distress=0.3, seed=3)
    sleep = weekly.word(weekly.BRAND_LINES[1], 190, weekly.WHITE, distress=0.3, seed=4)
    car_line = car_line.resize((860, int(car_line.height * 860 / car_line.width)), Image.LANCZOS)
    sleep = sleep.resize((640, int(sleep.height * 640 / sleep.width)), Image.LANCZOS)
    y = 150
    weekly.paste_shadowed(top, car_line, ((W - car_line.width) // 2, y))
    y += car_line.height + 8
    weekly.paste_shadowed(top, sleep, ((W - sleep.width) // 2, y))
    y += sleep.height + 30
    band = weekly.brush_band(760, 130, 7)
    top.alpha_composite(band, ((W - band.width) // 2, y))
    hours = weekly.word("8 HOURS", 100, weekly.NAVY, squeeze=0.95)
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
    d.text((W // 2, H - 170), "Full 8-hour video on the channel", font=f_small, fill=weekly.WHITE, anchor="ma")
    static = Image.alpha_composite(bg, Image.new("RGBA", (W, H), (0, 0, 0, 0)))

    # audio: start where the music is playing, if the album says where its tracks are
    start = 0.0
    tracks = os.path.splitext(args.audio)[0] + ".tracks.json"
    if os.path.exists(tracks):
        st = json.load(open(tracks)).get("track_starts") or []
        if st:
            start = st[0] + 40  # past the intro, into the groove
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    n = int(args.seconds * FPS)
    cmd = [ff, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-ss", f"{start:.2f}", "-t", str(args.seconds), "-i", args.audio,
           "-map", "0:v", "-map", "1:a",
           "-af", f"afade=t=in:d=1.5,afade=t=out:st={args.seconds - 2.5}:d=2.5",
           "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
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
        alpha = min(1.0, i / (FPS * 0.8), (n - 1 - i) / (FPS * 1.5))  # fade in / out from black
        rgb = frame.convert("RGB")
        if alpha < 1:
            rgb = Image.blend(Image.new("RGB", (W, H)), rgb, max(0.0, alpha))
        proc.stdin.write(rgb.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
