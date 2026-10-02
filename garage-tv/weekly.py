#!/usr/bin/env python3
"""Build this week's Mechanic Sleep video kit, hands-off.

Every week gets a different combination, chosen from the date so no state
file is needed:
  sound  : rain -> fan -> wind -> heater (changes every week)
  colour : none -> night -> amber -> cold (changes every 4 weeks)
  photo  : cycles through every picture in garage-tv/stills/ (add more any time)

Outputs in --outdir:
  mechanic-sleep-<tag>.zip   loop.mp4 + sound.wav + thumbnail.jpg + details.txt + make-8h.command
  thumbnail.jpg              1280x720 YouTube thumbnail
  details.txt / details.json title, description, tags, upload checklist
  TAG, RELEASE_TITLE         for the GitHub release step
  mechanic-sleep-8h.mp4      only with --full (the finished 8-hour video)

  python3 weekly.py --outdir kit              # this week's kit
  python3 weekly.py --outdir kit --date 2026-11-02 --full
"""
import argparse
import datetime as dt
import glob
import json
import math
import os
import random
import subprocess
import sys
import zipfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

LOOP_SECONDS = 60
AUDIO_MINUTES = 2
TOTAL_MINUTES = 480

RECIPE_ORDER = ["rain", "fan", "wind", "heater"]
GRADE_ORDER = ["none", "night", "amber", "cold"]

RECIPES = {
    "fan": dict(label="SHOP FAN", title="Garage Shop Fan Noise",
                scene="the big shop fans humming steady", tags=["fan noise", "shop fan", "fan sounds for sleep"]),
    "rain": dict(label="RAIN ON THE ROOF", title="Rain on the Shop Roof",
                 scene="rain drumming soft on the metal roof", tags=["rain sounds", "rain on roof", "rain for sleep"]),
    "heater": dict(label="SHOP HEATER", title="Shop Heater on a Cold Night",
                   scene="the unit heater running against the cold", tags=["heater sounds", "heater white noise"]),
    "wind": dict(label="WIND OUTSIDE", title="Wind Outside the Bay Door",
                 scene="wind pushing at the bay doors", tags=["wind sounds", "wind for sleep"]),
    "rain_road": dict(label="RAIN ON THE ROAD", title="Rain on a Mountain Road",
                      scene="steady rain falling over the road and the pines",
                      tags=["rain sounds", "rain for sleep", "rain on road"]),
}
GRADES = {
    "none": "at dusk, the last light going blue in the windows",
    "night": "deep into the night, long after the last tech clocked out",
    "amber": "with just the work lights still glowing",
    "cold": "on a winter night, frost on the glass",
}
BASE_TAGS = ["mechanic sleep", "garage ambience", "garage sounds", "white noise", "sleep sounds",
             "8 hours", "no music", "mechanic", "shop life", "auto shop ambience", "asmr garage"]

ORANGE = (247, 134, 30)
NAVY = (14, 24, 44)
WHITE = (246, 246, 250)


# --------------------------------------------------------------------------- choosing the week

def week_index(day):
    """Whole weeks since a fixed Monday, so every week maps to a stable number."""
    return (day - dt.date(2024, 1, 1)).days // 7


def photos():
    exts = ("*.jpg", "*.jpeg", "*.png", "*.webp")
    found = sorted(p for e in exts for p in glob.glob(os.path.join(HERE, "stills", e)))
    # one-off photos ("rotate": false in their .json) are built on request, never on the Sunday schedule
    found = [p for p in found if photo_meta(p).get("rotate", True)]
    if not found:
        sys.exit("no photos in garage-tv/stills/")
    return found


def photo_meta(photo):
    """Optional sidecar stills/<name>.json describing a photo that isn't the garage default:
    recipes, grades, title, title_tail, label, description, tags, text_side, rain, dust."""
    path = os.path.splitext(photo)[0] + ".json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def plan(day, photo=None, recipe=None, grade=None):
    i = week_index(day)
    iso = day.isocalendar()
    shots = photos()
    photo = photo or shots[i % len(shots)]
    meta = photo_meta(photo)
    # j counts how many times this photo has come up, so each photo walks through
    # all of its own sounds and colours no matter how many photos are in the rotation
    j = i // len(shots)
    recipes = meta.get("recipes", RECIPE_ORDER)
    grades = meta.get("grades", GRADE_ORDER)
    return dict(
        index=i,
        tag=f"garage-tv-{iso[0]}-W{iso[1]:02d}",
        recipe=recipe or recipes[j % len(recipes)],
        grade=grade or grades[(j // len(recipes)) % len(grades)],
        photo=photo,
        meta=meta,
    )


# --------------------------------------------------------------------------- words

def title_for(p):
    m = p.get("meta", {})
    mid = m.get("title", RECIPES[p["recipe"]]["title"])
    tail = m.get("title_tail", "Garage Ambience for Sleep")
    options = [
        f"Mechanic Sleep 8 Hours | {mid}, No Music, No Talking | {tail}",
        f"Mechanic Sleep 8 Hours | {mid} | No Music, No Talking",
        f"Mechanic Sleep 8 Hours | {mid}",
    ]
    return next(t for t in options if len(t) <= 100)


def label_for(p):
    return p.get("meta", {}).get("label", RECIPES[p["recipe"]]["label"])


def description_for(p):
    r = RECIPES[p["recipe"]]
    if p.get("meta", {}).get("description"):
        return p["meta"]["description"]
    return (
        f"The shop after everyone's gone home, {GRADES[p['grade']]}. A truck up on the lift, the floor still wet, "
        f"{r['scene']}. Eight hours of steady garage sound for sleeping, studying, or winding down after a long "
        f"day in the bay.\n\n"
        "No music. No talking. No sudden sounds. Seamless from start to finish, so nothing wakes you up.\n\n"
        "Built for mechanics, techs, and anyone who sleeps better with a fan running.\n\n"
        "Made by a mobile ADAS calibration tech. Absolute ADAS: https://absoluteadas.com\n\n"
        "#mechanicsleep #garageambience #whitenoise #sleepsounds #mechanic #shoplife"
    )


def tags_for(p):
    tags, total = [], 0
    for t in p.get("meta", {}).get("tags", []) + RECIPES[p["recipe"]]["tags"] + BASE_TAGS:
        if total + len(t) + 1 > 480:  # YouTube caps tags at 500 characters
            break
        tags.append(t)
        total += len(t) + 1
    return tags


# --------------------------------------------------------------------------- thumbnail

def cover(img, w, h):
    s = max(w / img.width, h / img.height)
    r = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def word(s, size, fill, squeeze=0.84, distress=0.0, seed=0):
    """Render text to a tight RGBA image, squeezed narrower and optionally roughed up."""
    f = ImageFont.truetype(BOLD, size)
    l, t, r, b = f.getbbox(s)
    im = Image.new("L", (r - l + 8, b - t + 8), 0)
    ImageDraw.Draw(im).text((4 - l, 4 - t), s, font=f, fill=255)
    im = im.resize((max(1, int(im.width * squeeze)), im.height), Image.LANCZOS)
    if distress:
        rnd = random.Random(seed)
        d = ImageDraw.Draw(im)
        for _ in range(int(im.width * im.height * distress / 60)):
            x, y = rnd.randrange(im.width), rnd.randrange(im.height)
            rr = rnd.choice((1, 1, 1, 1, 2))
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=0)
    out = Image.new("RGBA", im.size, fill + (0,))
    out.putalpha(im)
    return out


def paste_shadowed(canvas, img, xy, blur=6, offset=4, strength=200):
    a = img.split()[-1].point(lambda v: v * strength // 255)
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(a)
    pad = blur * 3
    big = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    big.paste(sh, (pad, pad))
    big = big.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(big, (xy[0] - pad + offset, xy[1] - pad + offset))
    canvas.alpha_composite(img, xy)


def brush_band(w, h, seed):
    """An orange paint-stroke band with ragged ends."""
    rnd = random.Random(seed)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    top = [(x, rnd.randint(0, 10)) for x in range(30, w - 30, 18)]
    bot = [(x, h - rnd.randint(0, 10)) for x in range(w - 30, 30, -18)]
    left = [(rnd.randint(0, 34), y) for y in range(h, 0, -10)]
    right = [(w - rnd.randint(0, 34), y) for y in range(0, h, 10)]
    d.polygon(top + right + bot + left, fill=ORANGE + (255,))
    for _ in range(26):  # dry-brush streaks along the ends
        y = rnd.randint(4, h - 4)
        x0 = rnd.choice((rnd.randint(0, 60), rnd.randint(w - 60, w)))
        d.line([(x0, y), (x0 + rnd.randint(-50, 50), y)], fill=(0, 0, 0, 0), width=rnd.randint(1, 3))
    return im


def waveform(w, h, seed):
    rnd = random.Random(seed)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    mid, cx, bars = h // 2, w // 2, 17
    gap = 9
    span = bars * gap
    d.line([(0, mid), (cx - span // 2 - 18, mid)], fill=WHITE + (255,), width=3)
    d.line([(cx + span // 2 + 18, mid), (w, mid)], fill=WHITE + (255,), width=3)
    for k in range(bars):
        x = cx - span // 2 + k * gap
        amp = (0.25 + 0.75 * math.sin(math.pi * (k + 0.5) / bars)) * (0.55 + 0.45 * rnd.random())
        half = int(amp * (h // 2 - 2))
        d.rounded_rectangle([x, mid - half, x + 3, mid + half], radius=2, fill=WHITE + (255,))
    return im


def make_thumbnail(p, out_path):
    sys.path.insert(0, HERE)
    from make_still_loop import grade  # same colour grade as the video

    right_side = p.get("meta", {}).get("text_side") == "right"
    bg = cover(grade(Image.open(p["photo"]).convert("RGB"), p["grade"]), 1280, 720).convert("RGBA")
    shade = Image.new("L", (1280, 720))
    ramp = [int(210 * max(0.0, 1 - (x / 1280) * 1.7)) for x in range(1280)]
    if right_side:
        ramp = ramp[::-1]
    shade.putdata(ramp * 720)
    bg = Image.composite(Image.new("RGBA", bg.size, (0, 0, 0, 255)), bg, shade)

    target = 640
    left = 70
    # draw the text block on its own layer so it can be scaled and moved per photo
    layer = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    mech = word("MECHANIC", 170, WHITE, distress=0.3, seed=p["index"])
    sleep = word("SLEEP", 196, WHITE, distress=0.3, seed=p["index"] + 1)
    mech = mech.resize((target, int(mech.height * target / mech.width)), Image.LANCZOS)
    sw = int(target * 0.74)
    sleep = sleep.resize((sw, int(sleep.height * sw / sleep.width)), Image.LANCZOS)
    paste_shadowed(layer, mech, (left, 70))
    paste_shadowed(layer, sleep, (left + (target - sleep.width) // 2, 70 + mech.height + 6))

    band_y = 70 + mech.height + sleep.height + 26
    band = brush_band(target + 40, 118, p["index"])
    layer.alpha_composite(band, (left - 20, band_y))
    hours = word("8 HOURS", 92, NAVY, squeeze=0.95)
    layer.alpha_composite(hours, (left - 20 + (band.width - hours.width) // 2, band_y + (band.height - hours.height) // 2))

    line = f"{label_for(p)}   |   NO MUSIC   |   NO TALKING"
    sub = word(line, 34, WHITE, squeeze=0.95)
    if sub.width > target + 20:
        sub = sub.resize((target + 20, int(sub.height * (target + 20) / sub.width)), Image.LANCZOS)
    sub_y = band_y + band.height + 30
    paste_shadowed(layer, sub, (left + (target - sub.width) // 2, sub_y), blur=3, offset=2)

    wave = waveform(520, 70, p["index"])
    layer.alpha_composite(wave, (left + (target - wave.width) // 2, sub_y + sub.height + 26))

    scale = float(p.get("meta", {}).get("text_scale", 1.0))
    bx, by, bx2, by2 = layer.getbbox()
    block = layer.crop((bx, by, bx2, by2))
    if scale != 1.0:
        block = block.resize((round(block.width * scale), round(block.height * scale)), Image.LANCZOS)
    x = 1280 - round(bx * scale) - block.width if right_side else bx
    bg.alpha_composite(block, (x, round(by * scale)))

    bg.convert("RGB").save(out_path, quality=90, optimize=True)


# --------------------------------------------------------------------------- build

def run(cmd):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True)


MAKE_8H = """#!/bin/bash
# Turns loop.mp4 + sound.wav into the finished 8-hour video.
# Easiest: open Terminal, type  bash  and a space, drag this file in, press Enter.
cd "$(dirname "$0")"
FF=""
for c in ./ffmpeg "$HOME/Downloads/ffmpeg" "$(command -v ffmpeg)"; do
  if [ -n "$c" ] && [ -x "$c" ]; then FF="$c"; break; fi
done
if [ -z "$FF" ]; then echo "Can't find ffmpeg. Put the ffmpeg file in your Downloads folder."; exit 1; fi
"$FF" -y -stream_loop {vloops} -i loop.mp4 -stream_loop {aloops} -i sound.wav -map 0:v:0 -map 1:a:0 \\
  -c:v copy -c:a aac -b:a 128k -t {seconds} -movflags +faststart "{name}"
echo
echo "Done: $(pwd)/{name}"
open . 2>/dev/null
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=os.path.join(HERE, "out", "weekly"))
    ap.add_argument("--date", help="build the kit for the week containing this date (YYYY-MM-DD); default tomorrow")
    ap.add_argument("--full", action="store_true", help="also build the finished 8-hour MP4")
    ap.add_argument("--crf", type=int, default=27)
    ap.add_argument("--photo", help="use this photo instead of the rotation (path or a name in stills/)")
    ap.add_argument("--recipe", help="force a sound recipe (rain, fan, wind, heater, rain_road)")
    ap.add_argument("--grade", help="force a colour grade (none, night, amber, cold)")
    ap.add_argument("--name", help="folder/tag name for a one-off kit (default: the week tag)")
    args = ap.parse_args()

    # default: the week that starts tomorrow, so the Sunday run builds the coming week's video
    day = dt.date.fromisoformat(args.date) if args.date else dt.date.today() + dt.timedelta(days=1)
    photo = args.photo
    if photo and not os.path.exists(photo):
        photo = os.path.join(HERE, "stills", photo)
    p = plan(day, photo=photo, recipe=args.recipe, grade=args.grade)
    if args.name:
        p["tag"] = args.name
    os.makedirs(args.outdir, exist_ok=True)
    print(json.dumps({k: (os.path.basename(v) if k == "photo" else v) for k, v in p.items()}, indent=2))

    folder = f"mechanic-sleep-{p['tag']}"
    stage = os.path.join(args.outdir, folder)
    os.makedirs(stage, exist_ok=True)
    loop, wav, thumb = (os.path.join(stage, n) for n in ("loop.mp4", "sound.wav", "thumbnail.jpg"))
    meta = p["meta"]
    final_name = f"mechanic-sleep-{meta.get('slug', p['recipe'].replace('_', '-'))}-8h.mp4"

    run([sys.executable, os.path.join(HERE, "make_ambience.py"), "--minutes", str(AUDIO_MINUTES),
         "--recipe", p["recipe"], "--seamless", "--seed", str(1000 + p["index"]), "--out", wav])
    run([sys.executable, os.path.join(HERE, "make_still_loop.py"), "--image", p["photo"],
         "--seconds", str(LOOP_SECONDS), "--grade", p["grade"], "--crf", str(args.crf),
         "--dust", str(meta.get("dust", 60)), "--rain", str(meta.get("rain", 0)),
         "--seed", str(p["index"]), "--out", loop])
    make_thumbnail(p, thumb)

    title, desc, tags = title_for(p), description_for(p), tags_for(p)
    details = dict(title=title, description=desc, tags=tags, categoryId="2",
                   madeForKids=False, alteredContent=True, recipe=p["recipe"], grade=p["grade"],
                   photo=os.path.basename(p["photo"]), tag=p["tag"])
    with open(os.path.join(args.outdir, "details.json"), "w") as f:
        json.dump(details, f, indent=2)
    txt = (f"TITLE\n{title}\n\nDESCRIPTION\n{desc}\n\nTAGS\n{', '.join(tags)}\n\n"
           "UPLOAD SETTINGS\n- Thumbnail: thumbnail.jpg\n- Audience: No, it's not made for kids\n"
           "- Altered or synthetic content: Yes\n- Category: Autos & Vehicles\n- Visibility: Public\n\n"
           "MAKE THE 8-HOUR FILE (Mac)\nOpen Terminal, type  bash  and a space, drag make-8h.command into the "
           f"window, press Enter. About 10 minutes. You get {final_name} in this folder.\n")
    for path in (os.path.join(stage, "details.txt"), os.path.join(args.outdir, "details.txt")):
        with open(path, "w") as f:
            f.write(txt)

    vloops = math.ceil(TOTAL_MINUTES * 60 / LOOP_SECONDS) - 1
    aloops = math.ceil(TOTAL_MINUTES / AUDIO_MINUTES) - 1
    with open(os.path.join(stage, "make-8h.command"), "w") as f:
        f.write(MAKE_8H.format(vloops=vloops, aloops=aloops, seconds=TOTAL_MINUTES * 60, name=final_name))

    zpath = os.path.join(args.outdir, f"{folder}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ("loop.mp4", "sound.wav", "thumbnail.jpg", "details.txt", "make-8h.command"):
            info = zipfile.ZipInfo(f"{folder}/{n}", date_time=dt.datetime.now().timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((0o755 if n.endswith(".command") else 0o644) | 0o100000) << 16
            with open(os.path.join(stage, n), "rb") as src:
                z.writestr(info, src.read())
    Image.open(thumb).save(os.path.join(args.outdir, "thumbnail.jpg"), quality=90)
    with open(os.path.join(args.outdir, "TAG"), "w") as f:
        f.write(p["tag"])
    with open(os.path.join(args.outdir, "RELEASE_TITLE"), "w") as f:
        f.write(f"Mechanic Sleep, week of {day - dt.timedelta(days=day.weekday())}: {meta.get('title', RECIPES[p['recipe']]['title'])}")

    if args.full:
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        run([ff, "-y", "-loglevel", "error", "-stream_loop", str(vloops), "-i", loop,
             "-stream_loop", str(aloops), "-i", wav, "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-t", str(TOTAL_MINUTES * 60),
             "-movflags", "+faststart", os.path.join(args.outdir, "mechanic-sleep-8h.mp4")])

    print(f"\nKIT READY: {zpath} ({os.path.getsize(zpath) / 1e6:.0f} MB)")
    print("TITLE:", title)


if __name__ == "__main__":
    main()
