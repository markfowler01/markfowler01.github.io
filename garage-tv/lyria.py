#!/usr/bin/env python3
"""Instrumental music from Google's Lyria models through the Gemini API (GEMINI_API_KEY).

  python3 lyria.py --prompt "calm deep-work electronic, 80 bpm, ..." --out track.mp3 [--model lyria-3.5]

Saves the audio the model returns and prints what came back (model, mime type, size, any text).
Music only: the prompt always asks for no vocals.
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
EXT = {"audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/L16": ".pcm",
       "audio/ogg": ".ogg", "audio/flac": ".flac", "audio/aac": ".aac", "audio/mp4": ".m4a"}


def generate(prompt, model="lyria-3.5", timeout=600):
    """[(mime type, bytes)] for every audio part, plus any text the model sent back."""
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["AUDIO"]}}
    req = urllib.request.Request(API.format(model=model), data=json.dumps(body).encode(), method="POST")
    req.add_header("x-goog-api-key", os.environ["GEMINI_API_KEY"])
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{model} said {e.code}: {e.read()[:600]!r}")
    audio, text = [], []
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                audio.append((inline.get("mimeType") or inline.get("mime_type") or "audio/unknown",
                              base64.b64decode(inline["data"])))
            elif part.get("text"):
                text.append(part["text"])
    if not audio:
        raise RuntimeError(f"{model} returned no audio: {json.dumps(data)[:600]}")
    return audio, " ".join(text), data.get("usageMetadata")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--model", default="lyria-3.5")
    ap.add_argument("--out", required=True, help="file name; the extension follows what the model returns")
    a = ap.parse_args()
    try:
        audio, text, usage = generate(a.prompt + " Instrumental only, no vocals, no lyrics.", a.model)
    except RuntimeError as e:
        sys.exit(str(e))
    base = os.path.splitext(a.out)[0]
    for i, (mime, raw) in enumerate(audio):
        path = base + (f"-{i}" if i else "") + EXT.get(mime.split(";")[0], ".bin")
        with open(path, "wb") as f:
            f.write(raw)
        print(f"{a.model}: wrote {path} ({mime}, {len(raw) / 1e6:.1f} MB)")
    print("text:", text[:500] if text else "-", "| usage:", usage)
