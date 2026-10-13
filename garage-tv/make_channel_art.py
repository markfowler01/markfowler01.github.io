#!/usr/bin/env python3
"""Make YouTube channel art from a still: thumbnail, banner, and profile picture.

  python3 make_channel_art.py --image stills/bay-dusk.webp --name "SHOP AFTER HOURS"

Outputs (in --outdir):
  thumbnail.jpg  1280x720,  under 2 MB  (video thumbnail)
  banner.jpg     2560x1440, text inside the 1546x423 safe area (channel banner)
  avatar.png     800x800    (profile picture; YouTube shows it as a circle)
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
AMBER = (247, 134, 30)  # same orange as the video thumbnails
WHITE = (245, 245, 250)


def cover(img, w, h, fx=0.5, fy=0.5):
    """Scale to cover w x h, crop around focus point (fx, fy)."""
    s = max(w / img.width, h / img.height)
    r = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x = int((r.width - w) * fx)
    y = int((r.height - h) * fy)
    return r.crop((x, y, x + w, y + h))


def shade(img, strength, side="left"):
    """Dark gradient so text stays readable."""
    w, h = img.size
    g = Image.new("L", (w, h))
    px = g.load()
    for x in range(w):
        t = x / w if side == "left" else 1 - x / w
        v = int(255 * strength * max(0.0, 1 - t * 1.6))
        for y in range(h):
            px[x, y] = v
    black = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(black, img, g)


def text(draw, xy, s, size, fill, font=BOLD, spacing=0, shadow=True, anchor="la"):
    f = ImageFont.truetype(font, size)
    if shadow:
        x, y = xy
        draw.text((x + size // 18, y + size // 18), s, font=f, fill=(0, 0, 0), anchor=anchor)
    draw.text(xy, s, font=f, fill=fill, anchor=anchor)
    return f


def fit_size(s, font, max_w, start):
    size = start
    while size > 10 and ImageFont.truetype(font, size).getlength(s) > max_w:
        size -= 2
    return size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--name", default="CAR PEOPLE SLEEP")
    ap.add_argument("--subtitle", default="rain  ·  garage  ·  white noise  ·  8 hours for sleep")
    ap.add_argument("--banner-focus", default="0.3,0.55", help="x,y focus (0-1) of the banner crop")
    ap.add_argument("--avatar-box", default="0.72,0.35,0.6",
                    help="centre x, centre y (0-1) and size (fraction of photo height) of the profile picture crop")
    ap.add_argument("--hours", default="8 HOURS")
    ap.add_argument("--keep-width", type=float, default=0.89,
                    help="fraction of the photo width to keep from the left (0.89 drops the wall sign in bay-dusk)")
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    src = Image.open(args.image).convert("RGB")
    if args.keep_width < 1:
        # trim the right edge (e.g. a wall sign) keeping 16:9
        w = int(src.width * args.keep_width)
        h = min(src.height, int(w * 9 / 16))
        top = (src.height - h) // 2
        src = src.crop((0, top, w, top + h))
    src = ImageEnhance.Brightness(src).enhance(1.08)

    # ---- thumbnail: crop left of the wall banner, big readable text on the left
    th = cover(src, 1280, 720, fx=0.15, fy=0.5)
    th = shade(th, 0.85, "left")
    d = ImageDraw.Draw(th)
    text(d, (64, 70), args.hours, 150, AMBER)
    text(d, (68, 250), "GARAGE", 96, WHITE)
    text(d, (68, 352), "AMBIENCE", 96, WHITE)
    text(d, (72, 490), "shop fan white noise", 40, WHITE, font=REG)
    text(d, (72, 540), "for sleep & focus", 40, WHITE, font=REG)
    th.save(os.path.join(args.outdir, "thumbnail.jpg"), quality=90)

    # ---- banner: full scene, darkened, title centred in the TV/desktop/phone safe area
    bfx, bfy = (float(v) for v in args.banner_focus.split(","))
    bn = cover(src, 2560, 1440, fx=bfx, fy=bfy)
    bn = ImageEnhance.Brightness(bn).enhance(0.55)
    band = Image.new("L", bn.size, 0)
    ImageDraw.Draw(band).rectangle([0, 1440 // 2 - 260, 2560, 1440 // 2 + 260], fill=150)
    band = band.filter(ImageFilter.GaussianBlur(90))
    bn = Image.composite(Image.new("RGB", bn.size, (0, 0, 0)), bn, band)
    d = ImageDraw.Draw(bn)
    size = fit_size(args.name, BOLD, 1450, 170)
    text(d, (1280, 690), args.name, size, WHITE, anchor="ms")
    text(d, (1280, 790), args.subtitle, 48, AMBER, font=REG, anchor="ms")
    bn.save(os.path.join(args.outdir, "banner.jpg"), quality=90)

    # ---- avatar: a square crop around the car, with a thin ring
    cx, cy, frac = (float(v) for v in args.avatar_box.split(","))
    side = frac * src.height
    x0 = min(max(0, cx * src.width - side / 2), src.width - side)
    y0 = min(max(0, cy * src.height - side / 2), src.height - side)
    av = src.crop((round(x0), round(y0), round(x0 + side), round(y0 + side))).resize((800, 800), Image.LANCZOS)
    ring = ImageDraw.Draw(av)
    ring.ellipse([12, 12, 788, 788], outline=AMBER, width=14)
    av.save(os.path.join(args.outdir, "avatar.png"))

    for n in ("thumbnail.jpg", "banner.jpg", "avatar.png"):
        p = os.path.join(args.outdir, n)
        print(f"{p}  {os.path.getsize(p) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
