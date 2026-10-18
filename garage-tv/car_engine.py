#!/usr/bin/env python3
"""Car engine: pick a random high-performance-but-obtainable car and a moody scene, have
Google's Nano Banana (GEMINI_API_KEY) or OpenAI's image model (OPENAI_API_KEY) paint it, and write the photo's settings
(title, description, tags, white-noise bed, rain, thumbnail text side) next to it.

  python3 car_engine.py --date 2026-10-12 --dry-run      # show the pick and the prompt
  GEMINI_API_KEY=... python3 car_engine.py --date 2026-10-12     # Nano Banana
  OPENAI_API_KEY=... python3 car_engine.py --date 2026-10-12     # ChatGPT images

Picks avoid repeating a car used in the last 20 videos or a scene used in the last 3
(read from published.json). Output: stills/<date>-<car>.webp + .json, marked rotate:false
so the old weekly rotation never reuses it; the daily queue picks it up as a fresh photo.
"""
import argparse
import base64
import datetime as dt
import io
import json
import os
import random
import re
import sys
import urllib.error
import urllib.request

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))

# Exotic cars only: supercars and hypercars, a different one every video.
CARS = [
    ("Ferrari 296 GTB", "Ferrari 296 GTB"), ("Ferrari SF90 Stradale", "Ferrari SF90"), ("Ferrari Roma", "Ferrari Roma"),
    ("Ferrari F8 Tributo", "Ferrari F8"), ("Ferrari 812 Superfast", "Ferrari 812"), ("Ferrari 12Cilindri", "Ferrari 12Cilindri"),
    ("Lamborghini Huracan STO", "Huracan STO"), ("Lamborghini Revuelto", "Lamborghini Revuelto"),
    ("Lamborghini Aventador SVJ", "Aventador SVJ"), ("Lamborghini Countach LPI 800-4", "Countach"),
    ("McLaren 750S", "McLaren 750S"), ("McLaren 720S", "McLaren 720S"), ("McLaren Artura", "McLaren Artura"),
    ("McLaren P1", "McLaren P1"), ("McLaren Senna", "McLaren Senna"),
    ("Porsche 911 GT3 RS", "911 GT3 RS"), ("Porsche 911 Turbo S", "911 Turbo S"), ("Porsche 918 Spyder", "918 Spyder"),
    ("Porsche Carrera GT", "Carrera GT"), ("Aston Martin Vantage", "Aston Martin Vantage"),
    ("Aston Martin DBS", "Aston Martin DBS"), ("Aston Martin Valkyrie", "Aston Martin Valkyrie"),
    ("Bugatti Chiron", "Bugatti Chiron"), ("Pagani Huayra", "Pagani Huayra"), ("Koenigsegg Jesko", "Koenigsegg Jesko"),
    ("Ford GT", "Ford GT"), ("Lexus LFA", "Lexus LFA"), ("Audi R8 V10", "Audi R8"),
    ("Mercedes-AMG GT Black Series", "AMG GT Black Series"), ("Mercedes-AMG One", "AMG One"),
    ("Maserati MC20", "Maserati MC20"), ("Rimac Nevera", "Rimac Nevera"), ("Nissan GT-R Nismo", "GT-R Nismo"),
    ("Acura NSX Type S", "NSX Type S"), ("Chevrolet Corvette ZR1", "Corvette ZR1"), ("Lotus Evija", "Lotus Evija"),
]
COLORS = ["rosso red", "gloss black", "chalk grey", "pearl white", "midnight blue", "british racing green",
          "papaya orange", "liquid silver", "satin black", "giallo yellow", "gunmetal grey", "deep burgundy"]

# The three PARKED FM series: how long the video runs, what sits under the lo-fi, the words.
SERIES = {
    "midnight_garage": dict(name="Midnight Garage", minutes=180, tail="Late-Night Lo-Fi for Work & Focus"),
    "rainy_drives": dict(name="Rainy Drives", minutes=480, tail="Lo-Fi & Rain for Sleep, Work & Focus"),
    "parked_peaceful": dict(name="Parked & Peaceful", minutes=240, tail="Calm Lo-Fi for Relaxing & Focus"),
}

# Scenes: where the car sits, its series, which ambience plays softly under the lo-fi, and rain on screen.
SCENES = [
    dict(id="skyline_garage", series="midnight_garage", bed="rain", rain=0,
         title="in a Garage Above the Rainy City",
         prompt="parked inside a warm modern luxury garage with floor-to-ceiling windows overlooking a rainy city skyline at night, rain on the glass, city lights reflecting",
         words="rain on the glass and the city glowing below"),
    dict(id="shop_night", series="midnight_garage", bed="fan", rain=0,
         title="in the Shop After Hours",
         prompt="inside a clean, dark high-end workshop after hours, parked in a service bay, warm work lights, polished floor",
         words="the shop after everyone has gone home, the fans still humming"),
    dict(id="home_garage", series="midnight_garage", bed="rain", rain=0,
         title="in the Garage on a Rainy Night",
         prompt="inside a cozy private garage at night with the door open to falling rain, warm string lights, a workbench",
         words="rain on the garage roof and a warm light on"),
    dict(id="parking_deck", series="midnight_garage", bed="heater", rain=0,
         title="on a Rooftop Parking Deck at Night",
         prompt="parked alone on the top floor of an empty parking garage at night, city lights in the distance",
         words="a quiet city humming below an empty rooftop deck"),
    dict(id="rain_mountain", series="rainy_drives", bed="rain_road", rain=900,
         title="in the Rain on a Mountain Road",
         prompt="parked on a wet mountain road overlook at dusk in steady rain, dark pine trees, low clouds over a lake below",
         words="rain falling over the pines and a lake below"),
    dict(id="neon_city", series="rainy_drives", bed="rain_road", rain=900,
         title="on a Rainy Neon Night",
         prompt="parked on an empty rain-soaked city street at night, soft neon signs reflecting in the wet asphalt",
         words="rain on an empty city street, neon reflecting in the puddles"),
    dict(id="forest_rain", series="rainy_drives", bed="rain_road", rain=900,
         title="on a Forest Road in the Rain",
         prompt="stopped on a narrow forest road at night in heavy rain, headlights on, mist between tall trees",
         words="heavy rain in a dark forest, mist between the trees"),
    dict(id="gas_station", series="rainy_drives", bed="rain_road", rain=700,
         title="at a Late-Night Gas Station",
         prompt="parked under the canopy of an empty modern gas station at 2 am in light rain, warm canopy lights",
         words="light rain at an empty gas station at 2 am"),
    dict(id="snow_cabin", series="parked_peaceful", bed="wind", rain=0,
         title="at a Cabin on a Snowy Night",
         prompt="parked outside a log cabin at night in gently falling snow, warm light in the windows",
         words="snow falling outside a warm cabin, wind in the trees"),
    dict(id="desert_dusk", series="parked_peaceful", bed="wind", rain=0,
         title="on a Desert Highway at Dusk",
         prompt="parked on the shoulder of an empty desert highway at blue hour, distant mountains, first stars",
         words="a warm desert wind on an empty highway at dusk"),
    dict(id="coast_fog", series="parked_peaceful", bed="wind", rain=0,
         title="on a Foggy Coast Road",
         prompt="parked at a pull-out on a foggy coastal cliff road at dawn, the ocean below fading into fog",
         words="fog rolling in off the ocean, a soft wind on the cliffs"),
    dict(id="mountain_overlook", series="parked_peaceful", bed="wind", rain=0,
         title="at a Mountain Overlook at Sunset",
         prompt="parked at a scenic mountain overlook at sunset, a wide valley below in golden haze",
         words="a soft wind at a mountain overlook as the sun goes down"),
    dict(id="lakeside_cafe", series="parked_peaceful", bed="rain", rain=0,
         title="Outside a Lakeside Cafe at Dusk",
         prompt="parked outside a small lakeside cafe at dusk in a light drizzle, warm window light, calm water",
         words="a light drizzle by the lake and warm light from the cafe"),
]

PROMPT = (
    "Photorealistic cinematic wide photograph, 16:9 framing, of a {color} {car} {scene}. "
    "The car sits in the left two-thirds of the frame in a three-quarter front view with its headlights on. "
    "The right third of the image is calm and uncluttered (sky, wall, road or fog) so text can go there. "
    "Moody, dark, relaxing late-night atmosphere, rich detail, wet reflections where it fits, shallow depth of field. "
    "Full-bleed image filling the entire frame edge to edge: no black bars, no letterboxing, no borders. "
    "No people, no text, no watermarks, no license plate numbers."
)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def pick(day, published):
    rng = random.Random(day.toordinal() * 7 + len(published))
    recent_cars = {e.get("car") for e in published[-20:]}
    recent_scenes = [e.get("scene") for e in published[-3:]]
    cars = [c for c in CARS if c[0] not in recent_cars] or CARS
    scenes = [s for s in SCENES if s["id"] not in recent_scenes] or SCENES
    car, short = rng.choice(cars)
    return dict(car=car, short=short, color=rng.choice(COLORS), scene=rng.choice(scenes))


def sidecar(choice):
    sc, short = choice["scene"], choice["short"]
    series = SERIES[sc["series"]]
    hours = series["minutes"] // 60
    title = f"{short} {sc['title']}"
    where = sc["title"].lower()
    return {
        "rotate": False,
        "recipes": ["lofi"],
        "bed": sc["bed"],
        "rain": sc["rain"],
        "dust": 0 if sc["rain"] else 40,
        "grades": ["none"],
        "minutes": series["minutes"],
        "series": series["name"],
        "text_side": "right",
        "text_scale": 0.66,
        "title": title,
        "title_tail": series["tail"],
        "label": series["name"].upper(),
        "slug": slug(short),
        "car": choice["car"],
        "scene": sc["id"],
        "tags": [choice["car"].lower(), short.lower(), series["name"].lower(), "exotic cars", "supercar",
                 "lofi for work", "focus music"],
        "description": (
            f"{series['name']}: a {choice['color']} {choice['car']} {where}, {sc['words']}. "
            f"{hours} hours of slow, original lo-fi with the weather soft underneath, for working, studying, "
            "relaxing or drifting off to sleep.\n\n"
            "No talking. No lyrics. No sudden sounds. Every track is original to this channel.\n\n"
            "PARKED FM | Dream Cars. Easy Listening.\n\n"
            f"#parkedfm #lofi #musicforwork #focusmusic #{slug(short).replace('-', '')}"
        ),
    }


def trim_bars(img, dark=14, spread=8):
    """Cut off black letterbox / pillarbox bars that image models sometimes add."""
    import numpy as np
    a = np.asarray(img.convert("L"), float)
    def flat_dark(lines):
        return (lines.mean(axis=1) < dark) & (lines.std(axis=1) < spread)
    rows, cols = flat_dark(a), flat_dark(a.T)
    top = int(np.argmin(rows)) if rows.any() else 0
    bottom = len(rows) - int(np.argmin(rows[::-1])) if rows.any() else len(rows)
    left = int(np.argmin(cols)) if cols.any() else 0
    right = len(cols) - int(np.argmin(cols[::-1])) if cols.any() else len(cols)
    if bottom - top < a.shape[0] * 0.5 or right - left < a.shape[1] * 0.5:
        return img  # a genuinely dark picture, not bars: leave it alone
    return img.crop((left, top, right, bottom))


def generate(prompt, out_path):
    """Paint the picture with whichever image service has a key: Google's Nano Banana
    (Gemini image model, GEMINI_API_KEY) first, else OpenAI (OPENAI_API_KEY)."""
    if os.environ.get("GEMINI_API_KEY"):
        try:
            return generate_gemini(prompt, out_path)
        except RuntimeError as e:
            if not os.environ.get("OPENAI_API_KEY"):
                raise
            print("Nano Banana failed, trying OpenAI:", e, file=sys.stderr)
    return generate_openai(prompt, out_path)


def generate_gemini(prompt, out_path):
    """Nano Banana: Gemini image model via the Gemini API, 16:9 output."""
    key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "16:9"}},
    }).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("x-goog-api-key", key)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gemini said {e.code}: {e.read()[:400]!r}")
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                img = trim_bars(Image.open(io.BytesIO(base64.b64decode(inline["data"]))).convert("RGB"))
                img.save(out_path, quality=92)
                return out_path
    raise RuntimeError(f"Gemini returned no image: {json.dumps(data)[:400]}")


def generate_openai(prompt, out_path):
    """OpenAI's image model (the one behind ChatGPT); save it as a 1536x1024 WebP."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    body = json.dumps({
        "model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        "prompt": prompt,
        "size": "1536x1024",
        "quality": os.environ.get("OPENAI_IMAGE_QUALITY", "high"),
        "n": 1,
    }).encode()
    req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenAI said {e.code}: {e.read()[:400]!r}")
    img = trim_bars(Image.open(io.BytesIO(base64.b64decode(data["data"][0]["b64_json"]))).convert("RGB"))
    img.save(out_path, quality=92)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (default today); the same date always gives the same pick")
    ap.add_argument("--dry-run", action="store_true", help="print the pick and prompt, call nothing")
    args = ap.parse_args()
    day = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    pub_path = os.path.join(HERE, "published.json")
    published = json.load(open(pub_path)) if os.path.exists(pub_path) else []

    choice = pick(day, published)
    prompt = PROMPT.format(color=choice["color"], car=choice["car"], scene=choice["scene"]["prompt"])
    meta = sidecar(choice)
    print(json.dumps(dict(car=choice["car"], color=choice["color"], scene=choice["scene"]["id"],
                          title=meta["title"], prompt=prompt), indent=2))
    if args.dry_run:
        return
    base = os.path.join(HERE, "stills", f"{day.isoformat()}-{slug(choice['short'])}")
    generate(prompt, base + ".webp")
    with open(base + ".json", "w") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    print("wrote", base + ".webp")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print("car engine:", e, file=sys.stderr)
        sys.exit(2)
