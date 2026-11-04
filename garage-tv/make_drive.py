#!/usr/bin/env python3
"""Night Drive (Mark, Nov 4: "a looping video of a car driving in various areas, very relaxing"):
a supercar cruising through different places, joined with soft crossfades, under our lofi music.

Each scene: Nano Banana paints the first frame in the PARKED FM drawn style, then a video model
(Google's Veo with the Gemini key, or OpenAI's Sora as a fallback) brings it to life as a steady
cruise. The clips are joined with crossfades; a long video repeats the set.

  python3 make_drive.py --out drive --music music.m4a            # the sample: four scenes, two views
  python3 make_drive.py --out drive --scenes city_chase,rain_pov  # only some scenes

Needs GEMINI_API_KEY (pictures, Veo) and/or OPENAI_API_KEY (Sora). Nothing is posted.
"""
import argparse
import base64
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import imageio_ffmpeg  # noqa: E402
from PIL import Image  # noqa: E402

CAR = "Porsche 911 Turbo S"
COLOR = "metallic red"

STYLE = ("A high-end, clean, stylized hand-drawn anime illustration, 16:9: a single still frame from a premium anime "
         "film, with crisp clean line work, cel shading and soft painterly lighting. ")
RULES = (" Calm, premium, relaxing late-night mood. One single continuous image, full-bleed, no black bars, no "
         "borders. No people visible, no text, no logos, no watermarks, no license plate numbers.")

# view: "chase" = the camera follows the car from outside; "pov" = from the driver's seat
SCENES = {
    "city_chase": dict(view="chase", place=(
        "a {color} {car} cruising down a wide rain-soaked city avenue at night, seen from behind and slightly to one "
        "side, its red taillights glowing; neon signs in soft pink, violet and blue reflect on the wet road; tall "
        "glass towers with lit windows, gentle rain")),
    "rain_pov": dict(view="pov", place=(
        "the view from the driver's seat of a {color} {car} on an empty highway at night in gentle rain: the "
        "dashboard glowing softly in warm orange at the bottom of the frame, the steering wheel partly visible, rain "
        "drops on the windshield, the road ahead lit by the headlights, distant city lights on the horizon")),
    "coast_chase": dict(view="chase", place=(
        "a {color} {car} cruising along a coastal highway at dusk, seen from behind and slightly above, the ocean on "
        "one side glowing with the last purple and orange light of sunset, street lamps just switching on, calm sea")),
    "snow_pov": dict(view="pov", place=(
        "the view from the driver's seat of a {color} {car} on a quiet mountain road at night with soft snow "
        "falling: the dashboard glowing softly in warm orange at the bottom of the frame, snowflakes drifting toward "
        "the windshield, snowy pine trees lit by the headlights, a calm deep-blue night sky")),
    "neon_chase": dict(view="chase", place=(
        "a {color} {car} driving slowly through a narrow neon-lit downtown street at night after the rain, seen from "
        "behind, glowing signs in pink, cyan and amber above small shops, wet reflections on the road")),
    "desert_chase": dict(view="chase", place=(
        "a {color} {car} cruising on a straight desert highway at twilight, seen from behind and slightly to one "
        "side, red rock mesas in silhouette, the sky fading from orange to deep violet, the first stars")),
}
SAMPLE = ["city_chase", "rain_pov", "coast_chase", "snow_pov"]

MOTION = {
    "chase": ("Bring this picture to life as one continuous, calm tracking shot: the camera glides smoothly behind "
              "the car at the same steady speed as it cruises forward, the scenery and lights flowing past slowly. "),
    "pov": ("Bring this picture to life as one continuous, calm shot from the driver's seat: the car cruises forward "
            "at a steady, relaxed speed, the road and lights flowing gently toward the camera. "),
}
MOTION_RULES = ("No cuts, no sudden moves, no other cars cutting in, no people, no hands, no text. Keep the same "
                "drawn anime style throughout. Peaceful and relaxing, like a late-night drive with music on.")


def paint(name, out_path):
    import car_engine as ce
    s = SCENES[name]
    prompt = STYLE + s["place"].format(color=COLOR, car=CAR) + "." + RULES
    for model in ("gemini-3-pro-image-preview", "gemini-2.5-flash-image"):
        try:
            return ce.gemini_image(model, prompt, out_path)
        except RuntimeError as e:
            print(f"{name}: {model} failed:", e, file=sys.stderr)
    raise RuntimeError(f"{name}: no picture")


# ----------------------------------------------------------------------------- Veo (Gemini API)

API = "https://generativelanguage.googleapis.com/v1beta"


def gcall(url, body=None, raw=False, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 method="POST" if body else "GET")
    req.add_header("x-goog-api-key", os.environ["GEMINI_API_KEY"])
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read() if raw else json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gemini said {e.code}: {e.read()[:400]!r}")


def veo_models():
    """Veo models this key can see, the fast ones first (cheaper), newest first."""
    if os.environ.get("VEO_MODEL"):
        return [os.environ["VEO_MODEL"]]
    try:
        names = [m["name"].split("/")[-1] for m in gcall(f"{API}/models?pageSize=1000").get("models", [])
                 if "veo" in m["name"] and "predictLongRunning" in m.get("supportedGenerationMethods", [])]
    except RuntimeError as e:
        print("couldn't list models:", e, file=sys.stderr)
        names = []
    names = names or ["veo-3.1-fast-generate-preview", "veo-3.0-fast-generate-001", "veo-3.0-generate-001",
                      "veo-2.0-generate-001"]
    def version(n):
        try:
            return float(n.split("-")[1])
        except (IndexError, ValueError):
            return 0.0
    names.sort(key=lambda n: ("fast" not in n, -version(n)))
    print("Veo models:", names, file=sys.stderr)
    return names


def veo(frame, prompt, out_clip, model):
    buf = io.BytesIO()
    Image.open(frame).convert("RGB").save(buf, "PNG")
    image = {"bytesBase64Encoded": base64.b64encode(buf.getvalue()).decode(), "mimeType": "image/png"}
    body = {"instances": [{"prompt": prompt, "image": image}], "parameters": {"aspectRatio": "16:9"}}
    op = gcall(f"{API}/models/{model}:predictLongRunning", body)
    deadline = time.time() + 20 * 60
    while not op.get("done"):
        if time.time() > deadline:
            raise RuntimeError("Veo took longer than 20 minutes")
        time.sleep(10)
        op = gcall(f"{API}/{op['name']}")
    if op.get("error"):
        raise RuntimeError(f"Veo error: {json.dumps(op['error'])[:300]}")
    resp = op.get("response", {})
    samples = (resp.get("generateVideoResponse") or resp).get("generatedSamples") or []
    if not samples:
        raise RuntimeError(f"Veo returned no video (maybe filtered): {json.dumps(resp)[:300]}")
    uri = samples[0]["video"]["uri"]
    with open(out_clip, "wb") as f:
        f.write(gcall(uri, raw=True, timeout=600))
    return out_clip


def animate(name, frame, out_clip, makers):
    prompt = MOTION[SCENES[name]["view"]] + MOTION_RULES
    errors = []
    for maker in makers:
        try:
            if maker == "sora":
                import car_engine as ce
                os.environ.setdefault("SORA_SECONDS", "12")
                ce.generate_sora(frame, prompt, out_clip)
            else:
                veo(frame, prompt, out_clip, maker)
            print(f"{name}: animated with {maker}", file=sys.stderr)
            return maker
        except Exception as e:  # try the next model
            errors.append(f"{maker}: {e}")
            print(f"{name}: {maker} failed:", e, file=sys.stderr)
    raise RuntimeError(f"{name}: no clip ({'; '.join(errors)[:600]})")


# ----------------------------------------------------------------------------- joining

def join(clips, music, out, fade=1.5, size=(1920, 1080)):
    """Crossfade the clips in order into one video, with the music (faded in and out) under it."""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    lens = [imageio_ffmpeg.count_frames_and_secs(c)[1] for c in clips]
    w, h = size
    parts, prev, offset = [], "v0", 0.0
    for i, c in enumerate(clips):
        parts.append(f"[{i}:v]fps=30,scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,"
                     f"format=yuv420p,settb=AVTB[v{i}]")
    for i in range(1, len(clips)):
        offset += lens[i - 1] - fade
        parts.append(f"[{prev}][v{i}]xfade=transition=fade:duration={fade}:offset={offset:.3f}[x{i}]")
        prev = f"x{i}"
    total = sum(lens) - fade * (len(clips) - 1)
    args = [ff, "-y", "-loglevel", "error"]
    for c in clips:
        args += ["-i", c]
    amap = []
    if music:
        args += ["-i", music]
        parts.append(f"[{len(clips)}:a]atrim=0:{total:.3f},afade=t=in:d=2,afade=t=out:st={total - 3:.3f}:d=3,"
                     f"volume=0.9[a]")
        amap = ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
    args += ["-filter_complex", ";".join(parts), "-map", f"[{prev}]", *amap, "-t", f"{total:.3f}",
             "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
             out]
    subprocess.run(args, check=True)
    return total


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--out", default="drive")
    ap.add_argument("--scenes", default=",".join(SAMPLE))
    ap.add_argument("--music")
    ap.add_argument("--makers", default="", help="comma list: Veo model names and/or 'sora' (default: Veo, then Sora)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    names = [n for n in a.scenes.split(",") if n]
    makers = [m for m in a.makers.split(",") if m]
    if not makers:
        makers = (veo_models() if os.environ.get("GEMINI_API_KEY") else []) + \
                 (["sora"] if os.environ.get("OPENAI_API_KEY") else [])

    def one(name):
        frame = os.path.join(a.out, f"{name}.png")
        clip = os.path.join(a.out, f"{name}.mp4")
        paint(name, frame)
        return name, clip, animate(name, frame, clip, makers)

    done = []
    with ThreadPoolExecutor(len(names)) as pool:
        for fut in [pool.submit(one, n) for n in names]:
            try:
                done.append(fut.result())
            except Exception as e:
                print("scene failed:", e, file=sys.stderr)
    order = [d for n in names for d in done if d[0] == n]
    report = {n: m for n, _, m in order}
    json.dump(report, open(os.path.join(a.out, "makers.json"), "w"), indent=1)
    print("made:", report)
    if not order:
        sys.exit("no scene came out")
    secs = join([c for _, c, _ in order], a.music, os.path.join(a.out, "drive-sample.mp4"))
    print(f"drive-sample.mp4: {secs:.1f} s from {len(order)} scenes")


if __name__ == "__main__":
    main()
