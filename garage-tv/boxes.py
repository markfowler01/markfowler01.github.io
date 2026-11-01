#!/usr/bin/env python3
"""Where things are in a picture, from Gemini: the car (to frame the Shorts) and the monitors (to make
their glow pulse in the video). Boxes are (x0, y0, x1, y1) fractions of the picture, cached per picture.

  boxes.find("stills/x.webp", "car")       -> [(0.29, 0.37, 0.74, 0.72)]
  boxes.find("stills/x.webp", "monitors")  -> [(0.09, 0.30, 0.15, 0.40), (0.16, 0.30, 0.22, 0.40)]
"""
import base64
import hashlib
import io
import json
import os
import re
import tempfile
import urllib.request

from PIL import Image

ASK = {
    "car": "Find the main car in this picture. Reply with JSON only: "
           '[{"box_2d": [ymin, xmin, ymax, xmax]}] on a 0-1000 scale, tight around the whole car.',
    "fire": "Find the flames of the fire in the fireplace in this picture (just the fire, not the whole fireplace). "
            'Reply with JSON only: [{"box_2d": [ymin, xmin, ymax, xmax]}] on a 0-1000 scale. Reply [] if there is no fire.',
    "windows": "Find the large glass windows in this picture (the glass, not the wall). Reply with JSON only: "
               '[{"box_2d": [ymin, xmin, ymax, xmax]}, ...] on a 0-1000 scale, one box per window or glass wall. '
               "Reply [] if there are none.",
    "monitors": "Find every glowing computer monitor or screen in this picture (not windows). Reply with JSON "
                'only: [{"box_2d": [ymin, xmin, ymax, xmax]}, ...] on a 0-1000 scale, tight around each screen. '
                "Reply [] if there are none.",
}


def find(path, what):
    """A list of boxes for `what` ("car" or "monitors"); [] if Gemini isn't there or finds nothing."""
    digest = hashlib.md5(open(path, "rb").read()).hexdigest()
    cache = os.path.join(tempfile.gettempdir(), f"boxes-{what}-{digest}.json")
    if os.path.exists(cache):
        return [tuple(b) for b in json.load(open(cache))]
    found = []
    if os.environ.get("GEMINI_API_KEY"):
        try:
            small = Image.open(path).convert("RGB")
            small.thumbnail((1024, 1024))
            buf = io.BytesIO()
            small.save(buf, "JPEG", quality=85)
            body = {"contents": [{"parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}},
                {"text": ASK[what]}]}]}
            model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-latest")
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                data=json.dumps(body).encode(), method="POST")
            req.add_header("x-goog-api-key", os.environ["GEMINI_API_KEY"])
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=90) as r:
                text = "".join(p.get("text", "") for p in json.load(r)["candidates"][0]["content"]["parts"])
            for m in re.finditer(r'"box_2d"\s*:\s*\[([^\]]*)\]', text):
                y0, x0, y1, x1 = [float(v) / 1000 for v in m.group(1).split(",")]
                if x1 > x0 and y1 > y0 and (x1 - x0) * (y1 - y0) < 0.9:
                    found.append((x0, y0, x1, y1))
            print(f"{what} from Gemini:", [[round(v, 3) for v in b] for b in found])
        except Exception as e:  # any failure: nothing found, the caller has a default
            print(f"{what}: Gemini didn't answer", repr(e)[:160])
    json.dump(found, open(cache, "w"))
    return found
