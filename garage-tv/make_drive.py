#!/usr/bin/env python3
"""Night Drive (Mark, Nov 4: "a looping video of a car driving in various areas, very relaxing"):
a supercar cruising through different places, joined with soft crossfades, under our lofi music.

Each scene: Nano Banana paints the first frame in the PARKED FM drawn style, then Gemini Omni Flash
(the Gemini key) brings it to life as a steady cruise. The clips are joined with crossfades; a long video repeats the set.

  python3 make_drive.py --out drive --music music.m4a            # the sample: four scenes, two views
  python3 make_drive.py --out drive --scenes city_chase,rain_pov  # only some scenes

Needs GEMINI_API_KEY (pictures and video). Nothing is posted.
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

# The car is the star (Mark, Nov 4: "it's also about the cars"): every scene shows it big and in view.
# view: "side" = the camera rolls alongside the car; "front" = the camera leads, the car follows it with
# its headlights on; "chase" = the camera follows behind and a little above; "pov" = the driver's seat
# with the car's real controls drawn faithfully (Mark: cool "if we get the controls for the cars right")
SCENES = {
    "city_side": dict(view="side", place=(
        "a {color} {car} cruising down a wide rain-soaked city avenue at night, seen from the side at the car's "
        "height, the whole car large in the frame and in sharp focus, glossy paint reflecting neon signs in pink, "
        "violet and blue, the city lights behind it softly blurred, wet road, gentle rain")),
    "highway_front": dict(view="front", place=(
        "a {color} {car} driving toward the camera on an empty highway at night in gentle rain, seen from the front "
        "three-quarter at a low angle, the car large in the frame, its headlights glowing and light bouncing off the "
        "wet road, highway lamps and distant city lights behind it")),
    "coast_chase": dict(view="chase", place=(
        "a {color} {car} cruising along a coastal highway at dusk, seen from behind three-quarter and slightly above, "
        "the car large in the frame with its taillights glowing, the ocean beside the road shining with the last "
        "purple and orange light of sunset, street lamps just switching on")),
    "snow_front": dict(view="front", place=(
        "a {color} {car} driving toward the camera on a quiet mountain road at night with soft snow falling, seen "
        "from the front three-quarter, the car large in the frame, headlights glowing through the snowflakes, snowy "
        "pine trees and a calm deep-blue night sky")),
    "neon_chase": dict(view="chase", place=(
        "a {color} {car} driving slowly through a narrow neon-lit downtown street at night after the rain, seen from "
        "behind three-quarter, the car large in the frame, glowing signs in pink, cyan and amber reflecting on its "
        "paint and on the wet road")),
    "desert_side": dict(view="side", place=(
        "a {color} {car} cruising on a straight desert highway at twilight, seen from the side at the car's height, "
        "the car large in the frame, red rock mesas in silhouette behind it, the sky fading from orange to deep "
        "violet")),
    "rain_pov": dict(view="pov", place=(
        "the view from the driver's seat of a {color} {car} on an empty highway at night in gentle rain, showing the "
        "real {car} interior faithfully: its own steering wheel design and badge-free hub, its own instrument "
        "cluster with softly glowing gauges, its own centre console and air vents, leather and stitching true to "
        "the real car, the dashboard glowing softly; rain drops on the windshield, the road ahead lit by the "
        "headlights, distant city lights on the horizon; no hands, no people")),
}
SAMPLE = ["city_side", "highway_front", "rain_pov", "coast_chase", "snow_front"]

MOTION = {
    "side": ("Bring this picture to life as one continuous, calm rolling shot: the camera travels alongside the car "
             "at exactly its speed, so the car stays in the same place in the frame, wheels turning, while the "
             "background and lights glide past behind it. "),
    "front": ("Bring this picture to life as one continuous, calm tracking shot: the camera moves backward ahead of "
              "the car at exactly its speed, so the car stays the same size in the frame as it cruises toward the "
              "camera, wheels turning, the road and lights flowing past. "),
    "chase": ("Bring this picture to life as one continuous, calm tracking shot: the camera glides behind the car at "
              "exactly its speed, so the car stays the same size in the frame as it cruises forward, the scenery and "
              "lights flowing past slowly. "),
    "pov": ("Bring this picture to life as one continuous, calm shot from the driver's seat: the car cruises forward "
            "at a steady, relaxed speed, the road and lights flowing gently toward the camera. The steering wheel, "
            "gauges and dashboard stay exactly as they are, steady and sharp; the wipers sweep slowly. "),
}
MOTION_RULES = ("The car keeps exactly the same shape, colour and details throughout. No cuts, no sudden moves, no "
                "other cars cutting in, no people, no hands, no text. Keep the same drawn anime style throughout. "
                "Peaceful and relaxing, like a late-night drive with music on.")


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


# ----------------------------------------------------------------------------- Gemini Omni Flash
# Google retired Veo for Gemini Omni Flash (Interactions API), and OpenAI shut the Sora API down
# (Sept 2026), so Omni is the video maker. One call returns the finished clip (3-10 s, with sound we
# don't use: the music goes on top).

API = "https://generativelanguage.googleapis.com/v1beta"
OMNI = os.environ.get("OMNI_MODEL") or "gemini-omni-1.1-flash"


def gcall(url, body=None, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 method="POST" if body else "GET")
    req.add_header("x-goog-api-key", os.environ["GEMINI_API_KEY"])
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gemini said {e.code}: {e.read()[:400]!r}")


def omni_video(interaction):
    """The base64 video in a finished interaction (REST: in the model_output step), or None."""
    for step in interaction.get("steps") or []:
        for c in step.get("content") or []:
            if c.get("type") == "video" and c.get("data"):
                return base64.b64decode(c["data"])
    out = interaction.get("output_video") or {}
    return base64.b64decode(out["data"]) if out.get("data") else None


def omni(frame, prompt, out_clip, model=OMNI):
    buf = io.BytesIO()
    Image.open(frame).convert("RGB").save(buf, "JPEG", quality=95)
    body = {
        "model": model,
        "input": [{"type": "image", "data": base64.b64encode(buf.getvalue()).decode(), "mime_type": "image/jpeg"},
                  {"type": "text", "text": prompt}],
        "response_format": {"type": "video", "aspect_ratio": "16:9", "resolution": "1080p"},
        "generation_config": {"video_config": {"task": "image_to_video"}},
    }
    it = gcall(f"{API}/interactions", body, timeout=1200)
    deadline = time.time() + 20 * 60
    while it.get("status") in ("queued", "in_progress", "pending", "running") and not omni_video(it):
        if time.time() > deadline:
            raise RuntimeError("Omni took longer than 20 minutes")
        time.sleep(10)
        it = gcall(f"{API}/interactions/{it['id']}")
    data = omni_video(it)
    if not data:
        raise RuntimeError(f"Omni returned no video (status {it.get('status')}): {json.dumps(it)[:400]}")
    with open(out_clip, "wb") as f:
        f.write(data)
    return out_clip


def animate(name, frame, out_clip, tries=2):
    prompt = MOTION[SCENES[name]["view"]] + MOTION_RULES
    for attempt in range(1, tries + 1):
        try:
            omni(frame, prompt, out_clip)
            print(f"{name}: animated with {OMNI}", file=sys.stderr)
            return OMNI
        except Exception as e:  # one retry: a busy service or a filtered clip
            print(f"{name}: try {attempt} failed:", e, file=sys.stderr)
            if attempt == tries:
                raise


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
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    names = [n for n in a.scenes.split(",") if n]

    def one(name):
        frame = os.path.join(a.out, f"{name}.png")
        clip = os.path.join(a.out, f"{name}.mp4")
        paint(name, frame)
        return name, clip, animate(name, frame, clip)

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
