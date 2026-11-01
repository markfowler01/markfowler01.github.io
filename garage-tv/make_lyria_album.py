#!/usr/bin/env python3
"""A music-day album made with Google's Lyria (lyria.py): new songs every video, in the flavours
Mark picked, joined with short silences, loudness-matched, music only.

  python3 make_lyria_album.py --songs 8 --seed 7 --flavors deep_focus,night_drive --out music.m4a
  python3 make_lyria_album.py --samples lab/          # one test song per flavour, to choose from

Writes music.m4a and music.tracks.json (minutes, track_starts, songs) like make_lofi_real.py.
Every prompt asks for an instrumental, clean studio mix: the channel never mixes noise into music. About $0.08 per song on the paid Gemini API (no free tier).
"""
import argparse
import concurrent.futures as cf
import json
import os
import random
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lyria  # noqa: E402
from make_lofi import SR, write_audio  # noqa: E402
from make_lofi_real import song_names  # noqa: E402

# Every prompt ends with this. Plain, positive wording: Lyria refused an earlier, longer list of
# "no ..." phrases as prohibited content. "Clean studio mix" keeps rain, hiss and crackle out; naming the
# only instruments keeps out the horns and saxophones Lyria likes to add to lo-fi (Mark, Nov 1).
COMMON = ("Instrumental only, no vocals. The only instruments are piano or electric piano, guitar, soft synth pads, "
          "bass and drums. A clean, smooth studio mix with a steady, gentle groove throughout.")
FLAVORS = {
    "deep_focus": "Deep work music for long focus sessions late at night. Calm, polished modern instrumental "
                  "electronic at about {bpm} BPM: warm analog synth pads, a soft deep sub bass, a gentle minimal "
                  "beat with soft kick and brushed hats, subtle {lead} motifs, slow evolving textures, wide stereo.",
    "night_drive": "Smooth night-drive chillwave at about {bpm} BPM: warm retro synths, a steady soft drum "
                   "machine groove, gentle arpeggios, a {lead} melody, the feeling of cruising through a city at "
                   "night, polished and relaxed.",
    "lofi_beats": "Mellow lo-fi hip hop at about {bpm} BPM: warm Rhodes chords, a soft head-nodding boom-bap "
                  "beat, round warm bass, a laid-back {lead} melody, relaxed and cosy, clean modern mix.",
    "ambient_piano": "Calm cinematic ambient for deep concentration at about {bpm} BPM: soft {lead} over warm "
                     "evolving pads, a very light pulse, spacious and peaceful, slow and steady.",
    "future_garage": "Atmospheric future garage and chillstep with a half-time feel around {bpm} BPM: airy "
                     "pads, a deep sub bass, soft shuffled drums, a delicate {lead} melody, night-time and dreamy.",
    "deep_house": "Smooth late-night deep house at about {bpm} BPM: warm jazzy chords, a soft four-on-the-floor "
                  "groove, a rolling bassline, a {lead} hook, lounge-like and polished.",
}
# The three packages from Mark's brief (Nov 1), its generator prompts word for word, plus the tempo and
# the video's key so the songs flow into each other (all 70-90 BPM, no vocals)
PACKAGES = {
    "grinder": "Dark synthwave, slow tempo, {bpm} BPM, atmospheric retro pads, minimalist driving bassline, "
               "no vocals, focus music.",
    "deep_work": "40Hz binaural beats, deep ambient drone, science focus soundscape, low cognitive load, space "
                 "ambient, cinematic pads, a slow pulse around {bpm} BPM.",
    "chill_trader": "Dark lofi hip hop, late night jazz chords, mellow aesthetic beat, {bpm} BPM, vinyl crackle, "
                    "cozy midnight vibe.",
}
PACKAGE_COMMON = "Instrumental only, no vocals. In {key}, steady and seamless from start to end."
FLAVORS.update(PACKAGES)
TEMPO = {"grinder": (80, 90), "deep_work": (70, 80), "chill_trader": (70, 74), "deep_focus": (74, 88), "night_drive": (86, 98), "lofi_beats": (70, 82), "ambient_piano": (60, 72),
         "future_garage": (130, 140), "deep_house": (116, 122)}
# no "synth lead" or vibraphone: Mark heard them (and jazzy wording) come out as a horn
LEADS = ["felt piano", "electric piano", "soft guitar", "warm synth pluck"]


def prompt_for(flavor, rng, mood="", lead=None, tempo=None, key="A minor"):
    """One song's description. lead: the main instrument (else a random one); tempo: slow or upbeat
    takes the lower or upper half of the flavour's tempo range. The brief's packages use its prompts
    as written (no mood or instrument words added), in the video's key."""
    lo, hi = TEMPO[flavor]
    mid = (lo + hi) // 2
    lo, hi = {"slow": (lo, mid), "upbeat": (mid, hi)}.get(tempo, (lo, hi))
    text = FLAVORS[flavor].format(bpm=rng.randint(lo, hi), lead=lead or rng.choice(LEADS))
    if flavor in PACKAGES:
        return f"{text} {PACKAGE_COMMON.format(key=key)}"
    return f"{text} {mood} {COMMON}".replace("  ", " ")


def decode(raw):
    """mp3 bytes -> float32 stereo at 44.1 kHz."""
    import imageio_ffmpeg
    out = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-i", "-", "-f", "f32le",
                          "-ac", "2", "-ar", str(SR), "-"], input=raw, capture_output=True, check=True).stdout
    return np.frombuffer(out, np.float32).reshape(-1, 2).astype(np.float64)


def one_song(flavor, seed, mood="", lead=None, tempo=None, model="lyria-3.5", tries=4, key="A minor"):
    """Lyria sometimes holds a song back because it may resemble an existing record; ask again with
    a slightly different take (tempo, lead) up to `tries` times. Held-back songs aren't charged."""
    for attempt in range(tries):
        rng = random.Random(seed + 7919 * attempt)
        prompt = prompt_for(flavor, rng, mood, lead if attempt < 2 else None, tempo, key)
        try:
            audio, _, _ = lyria.generate(prompt, model)
            break
        except RuntimeError as e:
            if attempt == tries - 1:
                raise
            print(f"take {attempt + 1} held back ({str(e)[:90]}...), trying another", file=sys.stderr)
    x = decode(audio[0][1])
    x = x / (np.sqrt((x ** 2).mean()) + 1e-9) * 0.1  # same loudness for every song
    n = min(len(x) // 4, int(1.5 * SR))
    x[:n] *= np.linspace(0, 1, n)[:, None]
    x[-n:] *= np.linspace(1, 0, n)[:, None]
    return x, prompt


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--songs", type=int, default=int(os.environ.get("LYRIA_SONGS", "8")))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--flavors", default=",".join(FLAVORS), help="comma-separated flavours to draw from")
    ap.add_argument("--mood", default="", help="extra words for every song, e.g. 'calm and steady'")
    ap.add_argument("--lead", help="main instrument for every song (else each song picks one)")
    ap.add_argument("--tempo", choices=["slow", "upbeat"], help="lower or upper half of the tempo range")
    ap.add_argument("--key", default="A minor", help="every song in this key, so they flow (A minor or E minor)")
    ap.add_argument("--gap", type=float, default=3.0)
    ap.add_argument("--bitrate", default="192k")
    ap.add_argument("--out", default="music.m4a")
    ap.add_argument("--samples", help="write one test song per flavour (mp3) into this folder instead")
    a = ap.parse_args()

    if a.samples:
        os.makedirs(a.samples, exist_ok=True)
        for i, fl in enumerate(FLAVORS):
            p = prompt_for(fl, random.Random(a.seed + i), a.mood)
            try:
                audio, _, _ = lyria.generate(p)
            except RuntimeError as e:
                print(f"{i + 1}-{fl} failed: {e}", file=sys.stderr)
                continue
            with open(os.path.join(a.samples, f"{i + 1}-{fl}.mp3"), "wb") as f:
                f.write(audio[0][1])
            print(f"{i + 1}-{fl}: {p}")
        return

    flavors = [f for f in a.flavors.split(",") if f in FLAVORS] or list(FLAVORS)
    rng = random.Random(a.seed)
    plan = [(rng.choice(flavors), a.seed * 100 + i) for i in range(a.songs)]
    songs = [None] * len(plan)
    with cf.ThreadPoolExecutor(4) as pool:
        futures = {pool.submit(one_song, fl, sd, a.mood, a.lead, a.tempo, key=a.key): i
                   for i, (fl, sd) in enumerate(plan)}
        for fut in cf.as_completed(futures):
            i = futures[fut]
            try:
                songs[i] = fut.result()
            except (RuntimeError, OSError, subprocess.CalledProcessError) as e:
                print(f"song {i + 1} failed:", e, file=sys.stderr)
    got = [(s, plan[i][0]) for i, s in enumerate(songs) if s]
    if len(got) < max(3, a.songs // 2):
        sys.exit(f"only {len(got)} of {a.songs} songs came back from Lyria")
    gap = np.zeros((int(a.gap * SR), 2))
    parts, starts, t = [], [], 0
    for (x, _), _fl in got:
        starts.append(round(t / SR, 2))
        parts += [x, gap]
        t += len(x) + len(gap)
    album = np.concatenate(parts)
    album *= 0.08 / (np.sqrt((album ** 2).mean()) + 1e-12)
    album = 0.9 * np.tanh(album / 0.9)  # music only: nothing else is mixed in
    write_audio(album, a.out, a.bitrate)
    names = song_names(len(got), a.seed)
    meta = dict(minutes=round(len(album) / SR / 60, 3), track_starts=starts, engine="lyria-3.5",
                songs=[dict(name=n, start=s, flavor=fl) for n, s, (_, fl) in zip(names, starts, got)])
    with open(os.path.splitext(a.out)[0] + ".tracks.json", "w") as f:
        json.dump(meta, f, indent=1)
    print(f"album: {len(got)} Lyria songs, {meta['minutes']:.1f} min -> {a.out}")


if __name__ == "__main__":
    main()
