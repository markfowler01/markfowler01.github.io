"""The opening statement: one short line in the Deep Work voice ("Nobody is coming to do it for
you."), shown big and glowing over the first seconds of the video and of each Short.

  layer = statement.layer("Nobody is coming to do it for you.", 1920, 1080)   # RGBA, same size
  frame = statement.over(frame_rgb, layer, t)                                 # t = seconds in

All lines are PARKED FM's own wording (no quotes from real people).
"""
import os
import textwrap

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
THIN = os.path.join(HERE, "fonts", "Montserrat.ttf")  # SIL Open Font License
FADE_IN, HOLD_UNTIL, GONE_AT = 0.6, 4.2, 5.2  # seconds


def layer(text, w, h, center_y=None, size=None, wrap=None):
    """The statement on a transparent layer, centred (or around center_y): thin white letters with a
    soft glow, over a gentle dark band so it reads on any picture."""
    size = size or int(h * 0.1)
    f = ImageFont.truetype(THIN, size)
    f.set_variation_by_name("Light")
    lines = textwrap.wrap(text.upper(), wrap or (16 if w < h else 22))
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    line_h = int(size * 1.35)
    widest = max(d.textlength(line, font=f) for line in lines)
    if widest > w * 0.9:  # shrink to fit
        size = int(size * w * 0.9 / widest)
        f = ImageFont.truetype(THIN, size)
        f.set_variation_by_name("Light")
        line_h = int(size * 1.35)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    mid = h // 2 if center_y is None else center_y
    y = mid - line_h * len(lines) // 2
    for line in lines:
        md.text((w // 2, y), line, font=f, fill=255, anchor="ma")
        y += line_h
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    band = Image.new("L", (w, h), 0)
    top = mid - line_h * len(lines) // 2 - size
    ImageDraw.Draw(band).rectangle([0, top, w, top + line_h * len(lines) + 2 * size], fill=120)
    out.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (w, h), 0)] * 3,
                                             band.filter(ImageFilter.GaussianBlur(size)))))
    for radius, strength, colour in ((size // 3, 110, (120, 200, 255)), (size // 10, 160, (210, 238, 255))):
        glow = mask.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: min(255, v * strength // 100))
        out.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (w, h), c) for c in colour], glow)))
    out.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (w, h), 248)] * 3, mask)))
    return out


def strength(t):
    """How visible the statement is t seconds in: fades in, holds, fades out, then gone."""
    if t >= GONE_AT:
        return 0.0
    if t < FADE_IN:
        return t / FADE_IN
    if t > HOLD_UNTIL:
        return (GONE_AT - t) / (GONE_AT - HOLD_UNTIL)
    return 1.0


def over(frame, text_layer, t):
    """frame (RGB or RGBA PIL image) with the statement on top at time t."""
    a = strength(t)
    if a <= 0:
        return frame
    lay = text_layer if a >= 1 else Image.merge(
        "RGBA", (*text_layer.split()[:3], text_layer.split()[3].point(lambda v: int(v * a))))
    out = frame.convert("RGBA")
    out.alpha_composite(lay)
    return out.convert(frame.mode)
