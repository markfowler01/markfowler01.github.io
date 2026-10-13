#!/usr/bin/env python3
"""Build a Car People Sleep video kit, hands-off.

Daily schedule (--daily, used by the GitHub workflow): next unused photo from stills/,
fresh original lo-fi album, numbered title; see plan_daily(). The weekly rotation below
is kept for ambience videos and one-off kits (--photo).

Every week gets a different combination, chosen from the date so no state
file is needed:
  sound  : rain -> fan -> wind -> heater (changes every week)
  colour : none -> night -> amber -> cold (changes every 4 weeks)
  photo  : cycles through every picture in garage-tv/stills/ (add more any time)

Outputs in --outdir:
  car-people-sleep-<tag>.zip   loop.mp4 + sound.wav + thumbnail.jpg + details.txt + make-8h.command
  thumbnail.jpg              1280x720 YouTube thumbnail
  details.txt / details.json title, description, tags, upload checklist
  TAG, RELEASE_TITLE         for the GitHub release step
  car-people-sleep-8h.mp4    only with --full (the finished 8-hour video)

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
LOFI_MINUTES = 30  # lo-fi album length; 16 plays fill 8 hours
TOTAL_MINUTES = 480

# Channel branding: the series name in titles, the two thumbnail lines, file names.
BRAND = "Car People Sleep"
BRAND_LINES = ("CAR PEOPLE", "SLEEP")
BRAND_SLUG = "car-people-sleep"

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
    "mix": dict(label="WHITE NOISE + LO-FI", title="White Noise & Lo-Fi",
                scene="steady white noise with lo-fi drifting in", tags=["white noise", "white noise for sleep", "lofi", "lofi for sleep"]),
    "lofi": dict(label="CHILL LO-FI", title="Chill Lo-Fi Beats",
                 scene="slow lo-fi beats playing low", tags=["lofi", "lofi beats", "lofi for sleep", "chill beats"]),
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
BED_WORDS = {"rain_road": "Rain Sounds", "rain": "Rain on the Roof", "fan": "Shop Fan Noise",
             "wind": "Wind Sounds", "heater": "Heater Hum"}
LOFI_TAGS = ["car people sleep", "lofi hip hop", "sleep music", "study music", "8 hours", "car lofi",
             "no lyrics", "chill music", "relaxing music", "mechanic"]
BASE_TAGS = ["car people sleep", "garage ambience", "garage sounds", "white noise", "sleep sounds",
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


PUBLISHED = os.path.join(HERE, "published.json")
DAILY_SOUND = "mix"  # white noise with an occasional original lo-fi track


def load_published():
    if os.path.exists(PUBLISHED):
        with open(PUBLISHED) as f:
            return json.load(f)
    return []


def all_photos():
    exts = ("*.jpg", "*.jpeg", "*.png", "*.webp")
    return sorted(p for e in exts for p in glob.glob(os.path.join(HERE, "stills", e)))


def plan_daily(day):
    """Daily schedule: the next photo nobody has seen yet (alphabetical, so name new ones
    01-..., 02-... to set the order). When the queue is empty, reuse the photo that was
    used longest ago with the next colour grade, so a day is never skipped."""
    published = load_published()
    shots = all_photos()
    if not shots:
        sys.exit("no photos in garage-tv/stills/")
    used = {}
    for e in published:
        used.setdefault(e["photo"], []).append(e["date"])
    fresh = [s for s in shots if os.path.basename(s) not in used]
    fresh.sort(key=lambda s: (not os.path.basename(s).startswith(day.isoformat()), os.path.basename(s)))
    if fresh:
        photo, uses = fresh[0], 0
    else:
        photo = min(shots, key=lambda s: max(used[os.path.basename(s)]))
        uses = len(used[os.path.basename(photo)])
    meta = photo_meta(photo)
    recipe = meta.get("daily_sound", DAILY_SOUND)
    vol = sum(1 for e in published if e.get("recipe") == recipe) + 1
    p = dict(
        index=(day - dt.date(2024, 1, 1)).days,
        tag=f"daily-{day.isoformat()}",
        recipe=recipe,
        grade=meta.get("grades", GRADE_ORDER)[uses % len(meta.get("grades", GRADE_ORDER))] if uses else "none",
        photo=photo,
        meta=meta,
        vol=vol,
        fresh=(uses == 0),
    )
    # a photo's own title / description only on its first lo-fi outing; reuses get a numbered title
    if not (p["fresh"] and recipe in meta.get("recipes", [recipe]) and meta.get("title")):
        p["title_override"] = {"lofi": f"Chill Lo-Fi Beats Vol. {vol}",
                               "mix": f"White Noise & Lo-Fi Vol. {vol}"}.get(recipe)
        p["generic_words"] = True
    return p


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
    bed = m.get("bed", "rain_road")
    if p.get("title_override"):  # daily reuse / no sidecar: numbered title, ignore the photo's own words
        mid, m = p["title_override"], {}
    tail = m.get("title_tail", {"lofi": "Lo-Fi for Sleep & Study", "mix": "White Noise & Lo-Fi for Sleep"}
                 .get(p["recipe"], "Garage Ambience for Sleep"))
    if p.get("title_override") and p["recipe"] == "mix":
        # the numbered title already says "White Noise & Lo-Fi", so end on the sound instead
        tail = BED_WORDS.get(bed, "Rain Sounds") + " for Sleep"
    if m.get("title_full"):
        return m["title_full"]
    if p["recipe"] in ("lofi", "mix"):
        short = "White Noise & Lo-Fi" if p["recipe"] == "mix" else "Lo-Fi"
        options = [f"{BRAND} 8 Hours | {mid} | {tail}", f"{BRAND} 8 Hours | {mid} | {short}", f"{BRAND} 8 Hours | {mid}"]
        return next(t for t in options if len(t) <= 100)
    options = [
        f"{BRAND} 8 Hours | {mid}, No Music, No Talking | {tail}",
        f"{BRAND} 8 Hours | {mid} | No Music, No Talking",
        f"{BRAND} 8 Hours | {mid}",
    ]
    return next(t for t in options if len(t) <= 100)


def label_for(p):
    return p.get("meta", {}).get("label", RECIPES[p["recipe"]]["label"])


def description_for(p):
    r = RECIPES[p["recipe"]]
    if p.get("meta", {}).get("description") and not p.get("generic_words"):
        return p["meta"]["description"]
    if p["recipe"] == "mix":
        return ("Eight hours of steady white noise with a slow, original lo-fi track drifting in now and then, "
                "for sleeping, studying, or winding down after a long day in the bay.\n\n"
                "No talking. No lyrics. No sudden sounds. Every track is original to this channel.\n\n"
                "Made by a mobile ADAS calibration tech. Absolute ADAS: https://absoluteadas.com\n\n"
                "#carpeoplesleep #whitenoise #lofi #sleepsounds")
    if p["recipe"] == "lofi":
        return ("Eight hours of slow, original lo-fi beats for sleeping, studying, or winding down after a long day "
                "in the bay. Soft keys, warm bass, quiet drums and a little vinyl crackle.\n\n"
                "No lyrics. No talking. Every track is original to this channel.\n\n"
                "Made by a mobile ADAS calibration tech. Absolute ADAS: https://absoluteadas.com\n\n"
                "#carpeoplesleep #lofi #lofibeats #sleepmusic #chillbeats")
    return (
        f"The shop after everyone's gone home, {GRADES[p['grade']]}. A truck up on the lift, the floor still wet, "
        f"{r['scene']}. Eight hours of steady garage sound for sleeping, studying, or winding down after a long "
        f"day in the bay.\n\n"
        "No music. No talking. No sudden sounds. Seamless from start to finish, so nothing wakes you up.\n\n"
        "Built for car people: mechanics, techs, and anyone who sleeps better with a fan running.\n\n"
        "Made by a mobile ADAS calibration tech. Absolute ADAS: https://absoluteadas.com\n\n"
        "#carpeoplesleep #garageambience #whitenoise #sleepsounds #mechanic #shoplife"
    )


def tags_for(p):
    tags, total = [], 0
    base = LOFI_TAGS if p["recipe"] in ("lofi", "mix") else BASE_TAGS
    for t in p.get("meta", {}).get("tags", []) + RECIPES[p["recipe"]]["tags"] + base:
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


def auto_side(photo):
    """Put the text on whichever side of the picture is calmer (less detail), so it stays off the car."""
    g = Image.open(photo).convert("L").resize((192, 108))
    edges = g.filter(ImageFilter.FIND_EDGES)
    w = edges.width
    import numpy as np
    a = np.asarray(edges, float)[: int(edges.height * 0.65)]  # the text sits in the upper part
    return "right" if a[:, int(w * 0.55):].mean() < a[:, : int(w * 0.45)].mean() else "left"


def make_thumbnail(p, out_path):
    sys.path.insert(0, HERE)
    from make_still_loop import grade  # same colour grade as the video

    meta = p.get("meta", {})
    side = meta.get("text_side") or auto_side(p["photo"])
    right_side = side == "right"
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
    mech = word(BRAND_LINES[0], 170, WHITE, distress=0.3, seed=p["index"])
    sleep = word(BRAND_LINES[1], 196, WHITE, distress=0.3, seed=p["index"] + 1)
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

    if p["recipe"] == "mix":
        line = f"{label_for(p)}   |   NO TALKING"
    else:
        middle = "NO LYRICS" if p["recipe"] == "lofi" else "NO MUSIC"
        line = f"{label_for(p)}   |   {middle}   |   NO TALKING"
    line = p.get("meta", {}).get("subline") or line
    sub = word(line, 34, WHITE, squeeze=0.95)
    if sub.width > target + 20:
        sub = sub.resize((target + 20, int(sub.height * (target + 20) / sub.width)), Image.LANCZOS)
    sub_y = band_y + band.height + 30
    paste_shadowed(layer, sub, (left + (target - sub.width) // 2, sub_y), blur=3, offset=2)

    wave = waveform(520, 70, p["index"])
    layer.alpha_composite(wave, (left + (target - wave.width) // 2, sub_y + sub.height + 26))

    # photos with no settings file get the smaller corner block that keeps the car clear
    scale = float(meta.get("text_scale", 1.0 if meta else 0.72))
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
# Turns loop.mp4 + {audio} into the finished 8-hour video.
# Easiest: open Terminal, type  bash  and a space, drag this file in, press Enter.
cd "$(dirname "$0")"
FF=""
for c in ./ffmpeg "$HOME/Downloads/ffmpeg" "$(command -v ffmpeg)"; do
  if [ -n "$c" ] && [ -x "$c" ]; then FF="$c"; break; fi
done
if [ -z "$FF" ]; then echo "Can't find ffmpeg. Put the ffmpeg file in your Downloads folder."; exit 1; fi
"$FF" -y -stream_loop {vloops} -i loop.mp4 -stream_loop {aloops} -i {audio} -map 0:v:0 -map 1:a:0 \\
  -c:v copy {acodec} -t {seconds} -movflags +faststart "{name}"
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
    ap.add_argument("--recipe", help="force a sound recipe (rain, fan, wind, heater, rain_road, lofi, mix)")
    ap.add_argument("--grade", help="force a colour grade (none, night, amber, cold)")
    ap.add_argument("--name", help="folder/tag name for a one-off kit (default: the week tag)")
    ap.add_argument("--daily", help=argparse.SUPPRESS, action="store_true")
    ap.add_argument("--record", action="store_true", help="log this video in published.json (the scheduled run does this)")
    ap.add_argument("--lofi-minutes", type=float, default=LOFI_MINUTES, help=argparse.SUPPRESS)
    args = ap.parse_args()

    # default: the week that starts tomorrow, so the Sunday run builds the coming week's video
    if args.daily:
        day = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
        p = plan_daily(day)
    else:
        day = dt.date.fromisoformat(args.date) if args.date else dt.date.today() + dt.timedelta(days=1)
        photo = args.photo
        if photo and not os.path.exists(photo):
            photo = os.path.join(HERE, "stills", photo)
        p = plan(day, photo=photo, recipe=args.recipe, grade=args.grade)
    if args.name:
        p["tag"] = args.name
    os.makedirs(args.outdir, exist_ok=True)
    print(json.dumps({k: (os.path.basename(v) if k == "photo" else v) for k, v in p.items()}, indent=2))

    folder = f"{BRAND_SLUG}-{p['tag']}"
    stage = os.path.join(args.outdir, folder)
    os.makedirs(stage, exist_ok=True)
    lofi = p["recipe"] in ("lofi", "mix")
    audio_name = "music.m4a" if lofi else "sound.wav"
    audio_minutes = args.lofi_minutes if lofi else AUDIO_MINUTES
    # the lo-fi album is already AAC with track fades, so it is stream-copied (no re-encode)
    acodec = ["-c:a", "copy"] if lofi else ["-c:a", "aac", "-b:a", "128k"]
    loop, wav, thumb = (os.path.join(stage, n) for n in ("loop.mp4", audio_name, "thumbnail.jpg"))
    meta = p["meta"]
    final_name = f"{BRAND_SLUG}-{meta.get('slug', p['recipe'].replace('_', '-'))}-8h.mp4"

    if lofi:
        seed = 5000 + p["index"] if args.daily else meta.get("music_seed", 1000 + p["index"])
        bed = ["--bed", meta.get("bed", "rain_road")] if p["recipe"] == "mix" else []
        run([sys.executable, os.path.join(HERE, "make_lofi.py"), "--minutes", str(audio_minutes),
             "--seed", str(seed), *bed, "--out", wav])
    else:
        run([sys.executable, os.path.join(HERE, "make_ambience.py"), "--minutes", str(AUDIO_MINUTES),
             "--recipe", p["recipe"], "--seamless", "--seed", str(1000 + p["index"]), "--out", wav])
    run([sys.executable, os.path.join(HERE, "make_still_loop.py"), "--image", p["photo"],
         "--seconds", str(LOOP_SECONDS), "--grade", p["grade"], "--crf", str(args.crf),
         "--dust", str(meta.get("dust", 60)), "--rain", str(meta.get("rain", 0)),
         "--seed", str(p["index"]), "--out", loop])
    make_thumbnail(p, thumb)

    title, desc, tags = title_for(p), description_for(p), tags_for(p)
    scene_line = title.split(" | ")[1] if " | " in title else title
    trailer = os.path.join(stage, "trailer.mp4")
    run([sys.executable, os.path.join(HERE, "make_trailer.py"), "--image", p["photo"], "--audio", wav,
         "--title", scene_line, "--label", label_for(p), "--out", trailer])
    short_title = f"{scene_line} | 8 Hours of {RECIPES[p['recipe']]['title']} #shorts"[:100]
    details = dict(title=title, description=desc, tags=tags, categoryId="2",
                   short_title=short_title,
                   short_description="The full 8-hour video is on the channel. #carpeoplesleep #sleep #shorts",
                   madeForKids=False, alteredContent=True, recipe=p["recipe"], grade=p["grade"],
                   photo=os.path.basename(p["photo"]), tag=p["tag"])
    with open(os.path.join(args.outdir, "details.json"), "w") as f:
        json.dump(details, f, indent=2)
    txt = (f"TITLE\n{title}\n\nDESCRIPTION\n{desc}\n\nTAGS\n{', '.join(tags)}\n\n"
           "UPLOAD SETTINGS\n- Thumbnail: thumbnail.jpg\n- Audience: No, it's not made for kids\n"
           "- Altered or synthetic content: Yes\n- Category: Autos & Vehicles\n- Visibility: Public\n\n"
           "MAKE THE 8-HOUR FILE (Mac)\nOpen Terminal, type  bash  and a space, drag make-8h.command into the "
           f"window, press Enter. About 10 minutes. You get {final_name} in this folder.\n\n"
           f"TRAILER (YouTube Short)\nUpload trailer.mp4 from the YouTube app (+ > Upload a video).\n"
           f"Title: {short_title}\nDescription: The full 8-hour video is on the channel. #carpeoplesleep #sleep #shorts\n"
           "After the full video is live, add it as the Short's Related video so viewers can tap through.\n")
    for path in (os.path.join(stage, "details.txt"), os.path.join(args.outdir, "details.txt")):
        with open(path, "w") as f:
            f.write(txt)

    vloops = math.ceil(TOTAL_MINUTES * 60 / LOOP_SECONDS) - 1
    aloops = math.ceil(TOTAL_MINUTES / audio_minutes) - 1
    with open(os.path.join(stage, "make-8h.command"), "w") as f:
        f.write(MAKE_8H.format(vloops=vloops, aloops=aloops, seconds=TOTAL_MINUTES * 60, name=final_name,
                               audio=audio_name, acodec=" ".join(acodec)))

    zpath = os.path.join(args.outdir, f"{folder}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ("loop.mp4", audio_name, "thumbnail.jpg", "trailer.mp4", "details.txt", "make-8h.command"):
            info = zipfile.ZipInfo(f"{folder}/{n}", date_time=dt.datetime.now().timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((0o755 if n.endswith(".command") else 0o644) | 0o100000) << 16
            with open(os.path.join(stage, n), "rb") as src:
                z.writestr(info, src.read())
    Image.open(thumb).save(os.path.join(args.outdir, "thumbnail.jpg"), quality=90)
    import shutil
    shutil.copy(trailer, os.path.join(args.outdir, "trailer.mp4"))
    with open(os.path.join(args.outdir, "TAG"), "w") as f:
        f.write(p["tag"])
    with open(os.path.join(args.outdir, "RELEASE_TITLE"), "w") as f:
        when = day.isoformat() if args.daily else f"week of {day - dt.timedelta(days=day.weekday())}"
        f.write(f"{when}: {title.replace(BRAND + ' ', '', 1)}")

    if args.full:
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        run([ff, "-y", "-loglevel", "error", "-stream_loop", str(vloops), "-i", loop,
             "-stream_loop", str(aloops), "-i", wav, "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "copy", *acodec, "-t", str(TOTAL_MINUTES * 60),
             "-movflags", "+faststart", os.path.join(args.outdir, f"{BRAND_SLUG}-8h.mp4")])

    if args.record:
        log = load_published()
        log.append(dict(date=day.isoformat(), photo=os.path.basename(p["photo"]), recipe=p["recipe"],
                        grade=p["grade"], title=title, tag=p["tag"],
                        car=meta.get("car"), scene=meta.get("scene")))
        with open(PUBLISHED, "w") as f:
            json.dump(log, f, indent=2)
            f.write("\n")
        print("recorded in", PUBLISHED)
    print(f"\nKIT READY: {zpath} ({os.path.getsize(zpath) / 1e6:.0f} MB)")
    print("TITLE:", title)


if __name__ == "__main__":
    main()
