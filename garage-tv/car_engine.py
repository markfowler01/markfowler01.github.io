#!/usr/bin/env python3
"""Car engine: pick a random exotic car and a moody scene, have
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_playlist  # noqa: E402

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

# The three PARKED FM series: how long the video runs, the title words.
SERIES = {
    "midnight_garage": dict(name="Midnight Garage", minutes=180, tail="Late-Night Lo-Fi for Work & Focus"),
    "rainy_drives": dict(name="Rainy Drives", minutes=480, tail="Rainy Night Lo-Fi for Sleep, Work & Focus"),
    "parked_peaceful": dict(name="Parked & Peaceful", minutes=240, tail="Calm Lo-Fi for Relaxing & Focus"),
}

# Videos alternate: one day lo-fi music only, the next day a soundscape only (no music), 8 hours
# for sleep. A soundscape day plays the scene's own sound or, now and then, plain brown or white noise.
SOUND_MINUTES = 480
SOUND_NAMES = {"rain_road": "Rain Sounds", "rain": "Rain Sounds", "wind": "Wind Sounds", "fan": "Fan Noise",
               "heater": "Heater Hum", "brown": "Brown Noise", "white": "White Noise"}
SOUND_WORDS = {"rain_road": "steady rain", "rain": "soft rain on the roof", "wind": "soft wind",
               "fan": "a steady fan", "heater": "a low heater hum", "brown": "deep brown noise",
               "white": "smooth white noise"}

# Scenes: where the car sits, its series, which ambience it would suit (only used by the white-noise mixes), and rain on screen.
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
    scene = rng.choice(scenes)
    last = published[-1].get("recipe") if published else None
    # music days alternate in only once the real-song library (garage-tv/music) is stocked
    soundscape = rng.choice([scene["bed"], scene["bed"], "brown", "white"])
    sound = "lofi" if last != "lofi" and make_playlist.music_ready() else soundscape
    return dict(car=car, short=short, color=rng.choice(COLORS), scene=scene, sound=sound)


def sidecar(choice):
    sc, short, sound = choice["scene"], choice["short"], choice.get("sound", "lofi")
    series = SERIES[sc["series"]]
    title = f"{short} {sc['title']}"
    where = sc["title"].lower()
    tag = slug(short).replace("-", "")
    meta = {
        "rotate": False,
        "recipes": [sound],
        "daily_sound": sound,
        "bed": sc["bed"],
        "rain": sc["rain"],
        "dust": 0 if sc["rain"] else 40,
        "grades": ["none"],
        "series": series["name"],
        "text_side": "right",
        "text_scale": 0.66,
        "title": title,
        "label": series["name"].upper(),
        "slug": slug(short),
        "car": choice["car"],
        "scene": sc["id"],
    }
    if sound == "lofi":
        hours = series["minutes"] // 60
        meta.update(
            minutes=series["minutes"],
            title_tail=series["tail"],
            tags=[choice["car"].lower(), short.lower(), series["name"].lower(), "exotic cars", "supercar",
                  "lofi for work", "focus music"],
            description=(
                f"{series['name']}: a {choice['color']} {choice['car']} {where}, {sc['words']}. "
                f"{hours} hours of slow, chill lo-fi, music only, for working, studying, "
                "relaxing or drifting off to sleep.\n\n"
                "No talking. No lyrics. No sudden sounds. Music from the YouTube Audio Library.\n\n"
                "PARKED FM | Dream Cars. Easy Listening.\n\n"
                f"#parkedfm #lofi #musicforwork #focusmusic #{tag}"
            ),
        )
    else:
        name = SOUND_NAMES[sound]
        hashtag = name.lower().replace(" ", "")
        meta.update(
            minutes=SOUND_MINUTES,
            title_tail=f"{name} for Sleep & Focus",
            sound_name=name,
            tags=[name.lower(), f"{name.lower()} for sleeping", "white noise", "sleep sounds", "no music",
                  choice["car"].lower(), short.lower(), "exotic cars", "supercar"],
            description=(
                f"{series['name']}: a {choice['color']} {choice['car']} {where}, {sc['words']}. "
                f"{SOUND_MINUTES // 60} hours of {SOUND_WORDS[sound]}, no music, for sleeping, studying, "
                "or blocking out the world while you work.\n\n"
                "No music. No talking. No sudden sounds. Seamless from start to finish, so nothing wakes you up.\n\n"
                "PARKED FM | Dream Cars. Easy Listening.\n\n"
                + " ".join(dict.fromkeys(f"#{h}" for h in ("parkedfm", hashtag, "sleepsounds", "whitenoise", tag)))
            ),
        )
    return meta


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


# The three-way test: Nano Banana photo, ChatGPT photo, and Sora (a ChatGPT photo brought to life
# as a moving clip). Each needs its key; Sora uses the OpenAI key.
MAKERS = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY", "sora": "OPENAI_API_KEY"}
CLIPS = os.path.join(HERE, "out", "clips")


def pick_maker(published, sound):
    """Each maker gets the same number of music days and of soundscape days (so the sound can't
    skew the views); a tie goes to the next maker after the one that did the last video of that kind."""
    makers = [m for m, k in MAKERS.items() if os.environ.get(k)]
    if len(makers) < 2:
        return makers[0] if makers else "gemini"
    group = [e["maker"] for e in published if e.get("maker") in MAKERS and (e.get("recipe") == "lofi") == (sound == "lofi")]
    counts = {m: group.count(m) for m in makers}
    low = min(counts.values())
    tied = [m for m in makers if counts[m] == low]
    if group and group[-1] in makers:
        after = makers[makers.index(group[-1]) + 1:] + makers[:makers.index(group[-1]) + 1]
        return next(m for m in after if m in tied)
    return tied[0]


def generate(prompt, out_path, maker="gemini"):
    """Paint the picture with the chosen maker (Google's Nano Banana, GEMINI_API_KEY, or OpenAI's
    image model behind ChatGPT, OPENAI_API_KEY), falling back to the other one if it fails.
    Returns the maker that actually painted it."""
    painters = ["gemini", "openai"]
    order = [maker] + [m for m in painters if m != maker]
    order = [m for m in order if os.environ.get(MAKERS[m])] or ["openai"]
    for i, m in enumerate(order):
        try:
            (generate_gemini if m == "gemini" else generate_openai)(prompt, out_path)
            return m
        except RuntimeError as e:
            if i == len(order) - 1:
                raise
            print(f"{m} failed, trying {order[i + 1]}:", e, file=sys.stderr)


def generate_gemini(prompt, out_path):
    """Nano Banana Pro at 2K (about 2752x1536, sharp at 1080p after the zoom), falling back to the
    original Nano Banana (about 1344x768) if Pro is unavailable."""
    models = [os.environ["GEMINI_IMAGE_MODEL"]] if os.environ.get("GEMINI_IMAGE_MODEL") else \
        ["gemini-3-pro-image-preview", "gemini-2.5-flash-image"]
    for i, model in enumerate(models):
        try:
            return gemini_image(model, prompt, out_path)
        except RuntimeError as e:
            if i == len(models) - 1:
                raise
            print(f"{model} failed, trying {models[i + 1]}:", e, file=sys.stderr)


def gemini_image(model, prompt, out_path):
    key = os.environ["GEMINI_API_KEY"]
    image_config = {"aspectRatio": "16:9"}
    if "pro" in model:
        image_config["imageSize"] = "2K"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": image_config},
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


SORA_PROMPT = (
    "Bring this photo to life as a calm, cinematic ambient shot. Locked-off tripod camera: the camera does not "
    "move, pan, zoom or cut at all. The {color} {car} stays perfectly still, parked, with its headlights on. "
    "Only gentle natural motion in the scene: {motion}. Slow, peaceful, relaxing. No people, no text, no new objects."
)


def scene_motion(scene):
    if scene.get("rain"):
        return "rain falling steadily, ripples and reflections shimmering on the wet ground, drifting mist"
    return "soft light flickering and glowing, slow drifting mist or clouds, gentle movement in the air"


def multipart(fields, files):
    """Encode a multipart/form-data body by hand (standard library only)."""
    boundary = "----parkedfm" + base64.b16encode(os.urandom(8)).decode()
    out = io.BytesIO()
    for k, v in fields.items():
        out.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, (name, data, ctype) in files.items():
        out.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\n'
                  f"Content-Type: {ctype}\r\n\r\n".encode())
        out.write(data)
        out.write(b"\r\n")
    out.write(f"--{boundary}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={boundary}"


def openai_call(url, data=None, ctype=None, method=None, raw=False, timeout=120):
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"))
    req.add_header("Authorization", f"Bearer {os.environ['OPENAI_API_KEY']}")
    if ctype:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read() if raw else json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenAI said {e.code}: {e.read()[:400]!r}")


def generate_sora(still_path, prompt, out_clip):
    """Animate the still with Sora (OpenAI Videos API): the photo is the first frame, 12 seconds."""
    import time
    model = os.environ.get("SORA_MODEL") or "sora-2"
    size = os.environ.get("SORA_SIZE") or ("1792x1024" if model == "sora-2-pro" else "1280x720")
    w, h = map(int, size.split("x"))
    img = Image.open(still_path).convert("RGB")
    s = max(w / img.width, h / img.height)  # cover the video frame, centre crop
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    img = img.crop(((img.width - w) // 2, (img.height - h) // 2, (img.width - w) // 2 + w, (img.height - h) // 2 + h))
    ref = io.BytesIO()
    img.save(ref, "JPEG", quality=95)
    body, ctype = multipart(dict(model=model, prompt=prompt, seconds=os.environ.get("SORA_SECONDS") or "12", size=size),
                            {"input_reference": ("first-frame.jpg", ref.getvalue(), "image/jpeg")})
    job = openai_call("https://api.openai.com/v1/videos", body, ctype)
    print("Sora job", job.get("id"), job.get("status"), file=sys.stderr)
    deadline = time.time() + 30 * 60
    while job.get("status") in ("queued", "in_progress"):
        if time.time() > deadline:
            raise RuntimeError("Sora took longer than 30 minutes")
        time.sleep(15)
        job = openai_call(f"https://api.openai.com/v1/videos/{job['id']}")
    if job.get("status") != "completed":
        raise RuntimeError(f"Sora job {job.get('status')}: {json.dumps(job.get('error'))[:300]}")
    os.makedirs(os.path.dirname(out_clip), exist_ok=True)
    with open(out_clip, "wb") as f:
        f.write(openai_call(f"https://api.openai.com/v1/videos/{job['id']}/content", raw=True, timeout=600))
    return out_clip


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
    maker = os.environ.get("MAKER") if os.environ.get("MAKER") in MAKERS else pick_maker(published, choice["sound"])
    print(json.dumps(dict(car=choice["car"], color=choice["color"], scene=choice["scene"]["id"],
                          sound=choice["sound"], maker=maker, title=meta["title"], prompt=prompt), indent=2))
    if args.dry_run:
        return
    base = os.path.join(HERE, "stills", f"{day.isoformat()}-{slug(choice['short'])}")
    meta["maker"] = generate(prompt, base + ".webp", "openai" if maker == "sora" else maker)
    if maker == "sora" and meta["maker"] == "openai":
        clip = os.path.join(CLIPS, os.path.basename(base) + ".mp4")
        try:
            generate_sora(base + ".webp", SORA_PROMPT.format(color=choice["color"], car=choice["car"],
                                                             motion=scene_motion(choice["scene"])), clip)
            meta["maker"], meta["motion_clip"] = "sora", os.path.relpath(clip, HERE)
        except RuntimeError as e:
            print("Sora failed; using the still photo today:", e, file=sys.stderr)
    with open(base + ".json", "w") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    print("wrote", base + ".webp", "painted by", meta["maker"])


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print("car engine:", e, file=sys.stderr)
        sys.exit(2)
