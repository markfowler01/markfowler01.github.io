#!/usr/bin/env python3
"""Car engine: pick a random high-performance-but-obtainable car and a moody scene, have
OpenAI's image model (the one behind ChatGPT) paint it, and write the photo's settings
(title, description, tags, white-noise bed, rain, thumbnail text side) next to it.

  python3 car_engine.py --date 2026-10-12 --dry-run      # show the pick and the prompt
  OPENAI_API_KEY=... python3 car_engine.py --date 2026-10-12

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

# Fast, attainable cars: things a mechanic or enthusiast could actually own or work on.
CARS = [
    ("Toyota GR Supra", "Supra"), ("Toyota GR Corolla", "GR Corolla"), ("Toyota GR86", "GR86"),
    ("Honda Civic Type R", "Civic Type R"), ("Acura Integra Type S", "Integra Type S"),
    ("Nissan Z", "Nissan Z"), ("Nissan GT-R", "GT-R"), ("Subaru WRX", "WRX"),
    ("Mazda MX-5 Miata", "Miata"), ("Hyundai Elantra N", "Elantra N"), ("Hyundai Ioniq 5 N", "Ioniq 5 N"),
    ("Volkswagen Golf R", "Golf R"), ("Ford Mustang Dark Horse", "Mustang Dark Horse"),
    ("Ford Mustang Shelby GT500", "GT500"), ("Chevrolet Camaro ZL1", "Camaro ZL1"),
    ("Chevrolet Corvette Stingray C8", "C8 Corvette"), ("Chevrolet Corvette Z06", "Corvette Z06"),
    ("Dodge Challenger SRT Hellcat", "Hellcat"), ("Dodge Charger Scat Pack", "Charger Scat Pack"),
    ("Cadillac CT5-V Blackwing", "CT5-V Blackwing"), ("BMW M2", "BMW M2"), ("BMW M3 Competition", "M3"),
    ("BMW M4", "M4"), ("Audi RS 3", "RS 3"), ("Audi RS 5", "RS 5"), ("Mercedes-AMG C 63", "C 63"),
    ("Porsche 911 Carrera S", "911 Carrera S"), ("Porsche 718 Cayman GT4", "Cayman GT4"),
    ("Porsche 911 GT3", "911 GT3"), ("Lexus RC F", "RC F"), ("Alfa Romeo Giulia Quadrifoglio", "Giulia QV"),
    ("Lotus Emira", "Emira"), ("Tesla Model 3 Performance", "Model 3 Performance"),
    ("Ford F-150 Raptor", "Raptor"), ("Ram 1500 TRX", "TRX"), ("Ford Bronco Raptor", "Bronco Raptor"),
    ("Mitsubishi Lancer Evolution X", "Evo X"), ("Subaru WRX STI", "WRX STI"),
]
COLORS = ["deep red", "gloss black", "nardo grey", "pearl white", "midnight blue", "dark green",
          "burnt orange", "silver", "satin black", "electric blue", "yellow", "gunmetal grey"]

# Scenes: where the car sits, which white noise plays under the lo-fi, and whether it rains.
SCENES = [
    dict(id="rain_mountain", bed="rain_road", rain=900, label="RAIN + LO-FI",
         title="in the Rain on a Mountain Road",
         prompt="parked on a wet mountain road overlook at dusk in steady rain, dark pine trees, low clouds over a lake below",
         words="rain falling over the pines and a lake below"),
    dict(id="neon_city", bed="rain_road", rain=900, label="RAIN + LO-FI",
         title="on a Rainy Neon Night",
         prompt="parked on an empty rain-soaked city street at night, soft neon signs reflecting in the wet asphalt",
         words="rain on an empty city street, neon reflecting in the puddles"),
    dict(id="forest_rain", bed="rain_road", rain=900, label="RAIN + LO-FI",
         title="on a Forest Road in the Rain",
         prompt="stopped on a narrow forest road at night in heavy rain, headlights on, mist between tall trees",
         words="heavy rain in a dark forest, mist between the trees"),
    dict(id="gas_station", bed="rain_road", rain=700, label="RAIN + LO-FI",
         title="at a Late-Night Gas Station",
         prompt="parked under the canopy of an empty retro gas station at 2 am in light rain, warm canopy lights",
         words="light rain at an empty gas station at 2 am"),
    dict(id="shop_night", bed="fan", rain=0, label="SHOP FAN + LO-FI",
         title="in the Shop After Hours",
         prompt="inside a clean, dark mechanic shop after hours, parked in a service bay, warm work lights, tool chests",
         words="the shop after everyone has gone home, the fans still humming"),
    dict(id="home_garage", bed="rain", rain=0, label="RAIN + LO-FI",
         title="in the Garage on a Rainy Night",
         prompt="inside a cozy home garage at night with the door open to falling rain, warm string lights",
         words="rain on the garage roof and a warm light on"),
    dict(id="snow_cabin", bed="wind", rain=0, label="WIND + LO-FI",
         title="at a Cabin on a Snowy Night",
         prompt="parked outside a log cabin at night in gently falling snow, warm light in the windows",
         words="snow falling outside a warm cabin, wind in the trees"),
    dict(id="desert_dusk", bed="wind", rain=0, label="WIND + LO-FI",
         title="on a Desert Highway at Dusk",
         prompt="parked on the shoulder of an empty desert highway at blue hour, distant mountains, first stars",
         words="a warm desert wind on an empty highway at dusk"),
    dict(id="coast_fog", bed="wind", rain=0, label="WIND + LO-FI",
         title="on a Foggy Coast Road",
         prompt="parked at a pull-out on a foggy coastal cliff road at dawn, the ocean below fading into fog",
         words="fog rolling in off the ocean, a soft wind on the cliffs"),
    dict(id="parking_deck", bed="heater", rain=0, label="WHITE NOISE + LO-FI",
         title="on a Rooftop Parking Deck at Night",
         prompt="parked alone on the top floor of an empty parking garage at night, city lights in the distance",
         words="a quiet city humming below an empty rooftop deck"),
]

PROMPT = (
    "Photorealistic cinematic wide photograph, 16:9 framing, of a {color} {car} {scene}. "
    "The car sits in the left two-thirds of the frame in a three-quarter front view with its headlights on. "
    "The right third of the image is calm and uncluttered (sky, wall, road or fog) so text can go there. "
    "Moody, dark, relaxing late-night atmosphere, rich detail, wet reflections where it fits, shallow depth of field. "
    "No people, no text, no watermarks, no license plate numbers."
)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def pick(day, published):
    rng = random.Random(day.toordinal())
    recent_cars = {e.get("car") for e in published[-20:]}
    recent_scenes = [e.get("scene") for e in published[-3:]]
    cars = [c for c in CARS if c[0] not in recent_cars] or CARS
    scenes = [s for s in SCENES if s["id"] not in recent_scenes] or SCENES
    car, short = rng.choice(cars)
    return dict(car=car, short=short, color=rng.choice(COLORS), scene=rng.choice(scenes))


def sidecar(choice):
    sc, short = choice["scene"], choice["short"]
    title = f"{short} {sc['title']}"
    return {
        "rotate": False,
        "recipes": ["mix"],
        "bed": sc["bed"],
        "rain": sc["rain"],
        "dust": 0 if sc["rain"] else 40,
        "grades": ["none"],
        "text_side": "right",
        "text_scale": 0.66,
        "title": title,
        "title_tail": "White Noise & Lo-Fi for Sleep",
        "label": sc["label"],
        "slug": slug(short),
        "car": choice["car"],
        "scene": sc["id"],
        "tags": [choice["car"].lower(), short.lower(), "car sleep video", "white noise for sleep", "lofi for sleep"],
        "description": (
            f"A {choice['color']} {choice['car']} {sc['title'].split(' ', 1)[0].lower()} {sc['title'].split(' ', 1)[1].lower()}: "
            f"{sc['words']}. Eight hours of steady white noise with a slow, original lo-fi track drifting in now and then, "
            "for sleeping, studying, or winding down after a long day in the bay.\n\n"
            "No talking. No lyrics. No sudden sounds. Every track is original to this channel.\n\n"
            "Built for mechanics, car people, and anyone who sleeps better with a little noise.\n\n"
            "Made by a mobile ADAS calibration tech. Absolute ADAS: https://absoluteadas.com\n\n"
            f"#carpeoplesleep #whitenoise #lofi #sleepsounds #{slug(short).replace('-', '')}"
        ),
    }


def generate(prompt, out_path):
    """Ask OpenAI's image model for the picture; save it as a 1536x1024 WebP."""
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
    img = Image.open(io.BytesIO(base64.b64decode(data["data"][0]["b64_json"]))).convert("RGB")
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
