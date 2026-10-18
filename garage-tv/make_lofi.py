#!/usr/bin/env python3
"""Compose an original, royalty-free lo-fi album for sleep videos.

Every track is generated from scratch (no samples, no borrowed music):
  keys   : FM electric piano playing jazzy 7th/9th chords, softly strummed, with tremolo
  bass   : warm round bass following the chord roots
  drums  : quiet, dusty, swung boom-bap (kick, snare, hats), humanised
  lead   : sparse pentatonic melody on a bell-like piano in some sections
  texture: tape wow and flutter and gentle saturation. Music only: never any hiss, crackle or noise

Tracks are 2.5-3.5 minutes with intro, verses, a breakdown and an outro. The album is
padded to exactly --minutes so an 8-hour video is a whole number of album repeats.

  python3 make_lofi.py --minutes 30 --out album.m4a           # AAC, ready to stream-copy
  python3 make_lofi.py --minutes 3 --out test.wav --seed 4     # quick listen
  python3 make_lofi.py --minutes 30 --bed rain_road --out mix.m4a   # white noise + occasional lo-fi
"""
import argparse
import json
import math
import os
import subprocess
import wave

import numpy as np

SR = 44100

QUALITY = {
    "maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "7": [0, 4, 7, 10],
    "maj9": [0, 4, 7, 11, 14], "m9": [0, 3, 7, 10, 14], "9": [0, 4, 7, 10, 14],
}
# (semitones above the key's tonic, chord quality), one chord per bar
PROGRESSIONS = [
    [(2, "m9"), (7, "9"), (0, "maj9"), (9, "m7")],      # ii  V  I  vi
    [(0, "maj7"), (9, "m9"), (5, "maj7"), (7, "9")],    # I  vi  IV  V
    [(5, "maj9"), (4, "m7"), (2, "m9"), (0, "maj7")],   # IV iii ii  I
    [(9, "m9"), (5, "maj7"), (0, "maj9"), (7, "9")],    # vi IV  I   V
    [(4, "m7"), (9, "m9"), (2, "m7"), (7, "7")],        # iii vi ii  V
    [(0, "maj9"), (4, "m7"), (5, "maj9"), (7, "9")],    # I  iii IV  V
]
PENTATONIC = [0, 2, 4, 7, 9]
DRUM_PATTERNS = [  # beats within a 4-beat bar
    dict(kick=[0, 2.5], snare=[1, 3]),
    dict(kick=[0, 0.75, 2.5], snare=[1, 3]),
    dict(kick=[0, 2.25, 2.75], snare=[1, 3]),
    dict(kick=[0, 1.5, 2.5], snare=[1, 3]),
]


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def fft_filter(x, lo=None, hi=None):
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(x.shape[0], 1 / SR)
    g = np.ones_like(f)
    if hi:
        g /= np.sqrt(1 + (f / hi) ** 4)
    if lo:
        g *= (f / lo) ** 2 / np.sqrt(1 + (f / lo) ** 4)
    if x.ndim == 2:
        g = g[:, None]
    return np.fft.irfft(X * g, n=x.shape[0], axis=0)


# --------------------------------------------------------------------------- instruments

def epiano(freq, dur, vel, rng, bright=1.0):
    """FM electric piano note (Rhodes-ish): bell attack that mellows as it decays."""
    rel = 0.18
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    decay = 1.1 + 0.9 * min(1.0, 220.0 / freq)
    env = (1 - np.exp(-t / 0.004)) * np.exp(-t / decay)
    env *= np.where(t > dur, np.exp(-(t - dur) / 0.08), 1.0)
    idx = bright * vel * (2.2 * np.exp(-t / 0.25) + 0.55)
    out = np.zeros(n)
    for cents in (-4, 4):  # two slightly detuned voices for width
        f = freq * 2 ** (cents / 1200)
        out += np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)))
    out += 0.09 * vel * np.exp(-t / 0.025) * np.sin(2 * np.pi * min(freq * 14, 9000) * t)  # tine "bark"
    return 0.5 * out * env * vel


def bass_note(freq, dur, vel):
    rel = 0.08
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    env = (1 - np.exp(-t / 0.008)) * np.exp(-t / 0.9) * np.where(t > dur, np.exp(-(t - dur) / 0.04), 1.0)
    return vel * env * (np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(4 * np.pi * freq * t))


def kick(vel, rng):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 48 + 70 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return vel * np.sin(ph) * np.exp(-t / 0.16) * (1 - np.exp(-t / 0.001))


def snare(vel, rng):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    noise = fft_filter(rng.standard_normal(n), lo=900, hi=5000)
    noise /= np.abs(noise).max() + 1e-9
    body = np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.05)
    return vel * (1.0 * noise * np.exp(-t / 0.1) + 0.4 * body)


def hat(vel, rng):
    n = int(0.08 * SR)
    t = np.arange(n) / SR
    noise = fft_filter(rng.standard_normal(n), lo=5000, hi=12000)
    noise /= np.abs(noise).max() + 1e-9
    return vel * noise * np.exp(-t / 0.022)


def piano(freq, dur, vel, rng):
    """Soft acoustic-style piano: slightly stretched partials that die away faster the higher they are."""
    rel = 0.35
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    tau0 = 1.2 + 2.2 * min(1.0, 160.0 / freq)  # low notes ring longer
    out = np.zeros(n)
    for k in range(1, 9):
        fk = k * freq * np.sqrt(1 + 0.0004 * k * k)
        if fk > 9000:
            break
        amp = (1.0 / k ** 1.3) * (0.6 + 0.4 * vel) ** (k - 1)
        out += amp * np.exp(-t / (tau0 / (1 + 0.55 * (k - 1)))) * np.sin(2 * np.pi * fk * t + rng.uniform(0, 6.28))
    thump = fft_filter(rng.standard_normal(min(n, int(0.02 * SR))), hi=900)
    out[: len(thump)] += 0.08 * thump * np.exp(-np.arange(len(thump)) / (0.004 * SR))
    env = (1 - np.exp(-t / 0.003)) * np.where(t > dur, np.exp(-(t - dur) / 0.12), 1.0)
    return 0.45 * vel * out * env


def ride(vel, rng):
    """Jazz ride cymbal: a bright, shimmering ping that rings briefly."""
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    tone = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) for f in (3150, 4120, 5310, 6740))
    hiss = fft_filter(rng.standard_normal(n), lo=4000, hi=11000)
    hiss /= np.abs(hiss).max() + 1e-9
    return vel * (0.18 * tone * np.exp(-t / 0.22) + 0.5 * hiss * np.exp(-t / 0.3)) * (1 - np.exp(-t / 0.0015))


def brush(vel, rng):
    """Brush on the snare: a soft swish rather than a crack."""
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    noise = fft_filter(rng.standard_normal(n), lo=600, hi=3500)
    noise /= np.abs(noise).max() + 1e-9
    return vel * noise * (1 - np.exp(-t / 0.02)) * np.exp(-t / 0.12)


def reverb(x, seconds=2.2, wet=0.2, seed=0):
    """Room reverb: convolve with a decaying, darkening noise tail (FFT convolution)."""
    rng = np.random.default_rng(seed)
    m = int(seconds * SR)
    t = np.arange(m) / SR
    ir = rng.standard_normal((m, 2)) * np.exp(-t / (seconds / 6.9))[:, None]
    ir = fft_filter(ir, lo=200, hi=5000)
    ir /= np.sqrt((ir ** 2).sum(axis=0)) + 1e-12
    n = x.shape[0] + m
    nfft = 1 << (n - 1).bit_length()
    X = np.fft.rfft(x, nfft, axis=0)
    w = np.fft.irfft(X * np.fft.rfft(ir, nfft, axis=0), nfft, axis=0)[: x.shape[0]]
    return (1 - wet) * x + wet * w


def add(buf, sig, start, pan=0.0):
    """Mix a mono signal into a stereo buffer at sample `start` with constant-power pan."""
    s = int(start)
    if s >= buf.shape[0] or s + len(sig) <= 0:
        return
    if s < 0:
        sig, s = sig[-s:], 0
    e = min(buf.shape[0], s + len(sig))
    a = (pan + 1) * math.pi / 4
    buf[s:e, 0] += sig[: e - s] * math.cos(a)
    buf[s:e, 1] += sig[: e - s] * math.sin(a)


# --------------------------------------------------------------------------- composition

def voice(root_midi, quality, center):
    """Place chord tones (root left out, the bass has it) close to `center` for smooth voice leading."""
    notes = []
    for iv in QUALITY[quality][1:]:
        m = root_midi + iv
        while m - center > 6:
            m -= 12
        while center - m > 6:
            m += 12
        notes.append(m)
    return sorted(notes)


def arrangement(total_bars, rng):
    """List of (section, bars). Intro and outro are 4 bars; the middle fills the rest."""
    middle = total_bars - 8
    plan = [("intro", 4)]
    blocks = []
    while middle > 0:
        for name, size in (("A", 8), ("B", 8), ("break", 4), ("A", 8)):
            if middle <= 0:
                break
            take = min(size, middle)
            blocks.append((name, take))
            middle -= take
    return plan + blocks + [("outro", 4)]


def compose_track(seed, bars, style="lofi"):
    """style: lofi (boom-bap lo-fi), jazz (chill jazz: brushes, ride, walking bass),
    piano (soft piano and ambient: no drums, broken chords, reverb)."""
    rng = np.random.default_rng(seed)
    bpm = {"lofi": rng.uniform(70, 82), "jazz": rng.uniform(66, 78), "piano": rng.uniform(58, 68)}[style]
    beat = 60.0 / bpm
    bar = 4 * beat
    key = int(rng.choice([57, 58, 60, 62, 63, 65]))  # A, Bb, C, D, Eb, F (tonic, MIDI)
    progA = PROGRESSIONS[rng.integers(len(PROGRESSIONS))]
    progB = PROGRESSIONS[rng.integers(len(PROGRESSIONS))]
    drums = DRUM_PATTERNS[rng.integers(len(DRUM_PATTERNS))]
    swing = rng.uniform(0.08, 0.13) if style == "lofi" else rng.uniform(0.15, 0.19)  # late offbeats

    length = int((bars * bar + 3.0) * SR)
    keys = np.zeros((length, 2))
    low = np.zeros((length, 2))
    kit = np.zeros((length, 2))
    lead = np.zeros((length, 2))

    def hum(sec=0.008):
        return rng.normal(0, sec) * SR

    sections = arrangement(bars, rng)
    motif = None
    b0 = 0
    center = 64
    for name, nbars in sections:
        for k in range(nbars):
            bi = b0 + k
            t0 = bi * bar * SR
            prog = progB if name == "B" else progA
            deg, q = prog[bi % 4]
            root = key + deg
            # keys: strummed chord on 1, a softer re-voice on the "and of 2" or 3 sometimes
            notes = voice(root, q, center)
            center = int(np.mean(notes))
            soft = 0.55 if name in ("intro", "outro", "break") else 0.7
            if style == "piano":
                pattern = rng.choice([[0, 1, 2, 1, 3, 1, 2, 1], [0, 2, 1, 3, 2, 1, 3, 2], [0, 1, 2, 3, 2, 1, 2, 3]])
                pool = notes + [notes[0] + 12]
                for e, idx in enumerate(pattern):
                    m = pool[idx % len(pool)]
                    add(keys, piano(mtof(m), beat * 1.6, 0.42 * rng.uniform(0.8, 1.0), rng),
                        t0 + e * 0.5 * beat * SR + hum(0.006), pan=(m - 64) / 40)
                add(low, piano(mtof(root - 12 if root - 12 >= 40 else root), bar * 1.0, 0.5, rng), t0 + hum(0.004))
                notes = []
            for j, m in enumerate(notes):
                add(keys, epiano(mtof(m), bar * 0.95, soft * rng.uniform(0.8, 1.0), rng),
                    t0 + j * rng.uniform(0.008, 0.022) * SR + hum(), pan=rng.uniform(-0.35, 0.35))
            if style != "piano" and name in ("A", "B") and rng.random() < 0.45:
                at = rng.choice([1.5, 2.0, 2.5])
                for m in notes[1:]:
                    add(keys, epiano(mtof(m), beat * 1.2, 0.35 * rng.uniform(0.8, 1.0), rng, bright=0.7),
                        t0 + at * beat * SR + hum(), pan=rng.uniform(-0.3, 0.3))
            # bass: root on 1, fifth or approach note late in the bar
            if style == "jazz" and name not in ("intro", "outro"):
                bm = root - 24 if root - 24 >= 33 else root - 12
                nxt = key + prog[(bi + 1) % 4][0]
                nb = nxt - 24 if nxt - 24 >= 33 else nxt - 12
                tones = [bm, bm + QUALITY[q][1], bm + 7, nb + rng.choice([-1, 1])]  # root, 3rd, 5th, approach
                for qn, m in enumerate(tones):
                    add(low, bass_note(mtof(m), beat * 0.9, 0.8 if qn == 0 else 0.62), t0 + qn * beat * SR + hum(0.006))
            elif style == "lofi" and name not in ("intro", "outro"):
                bm = root - 24 if root - 24 >= 33 else root - 12
                add(low, bass_note(mtof(bm), beat * 1.6, 0.85), t0 + hum(0.004))
                if rng.random() < 0.6:
                    nxt = key + prog[(bi + 1) % 4][0]
                    approach = rng.choice([bm + 7, (nxt - 24 if nxt - 24 >= 33 else nxt - 12) - 1])
                    add(low, bass_note(mtof(approach), beat * 0.8, 0.6), t0 + 3 * beat * SR + hum(0.004))
            # drums: swung, quiet, humanised; out for intro / break / outro
            if style == "jazz" and name in ("A", "B"):
                for pos in (0, 1, 1 + 2 / 3, 2, 3, 3 + 2 / 3):  # spang, spang-a-lang
                    add(kit, ride((0.5 if pos in (1, 3) else 0.38) * rng.uniform(0.8, 1.0), rng),
                        t0 + pos * beat * SR + hum(0.006), pan=0.3)
                for b in (1, 3):
                    add(kit, brush(0.55 * rng.uniform(0.8, 1.0), rng), t0 + b * beat * SR + hum(0.008), pan=-0.1)
                for b in range(4):  # feathered kick, felt more than heard
                    add(kit, kick(0.28 * rng.uniform(0.8, 1.0), rng), t0 + b * beat * SR + hum(0.005))
            if style == "lofi" and name in ("A", "B"):
                for b in drums["kick"]:
                    add(kit, kick(0.9 * rng.uniform(0.85, 1.0), rng), t0 + b * beat * SR + hum(0.005))
                for b in drums["snare"]:
                    add(kit, snare(0.75 * rng.uniform(0.85, 1.0), rng), t0 + (b * beat + 0.012) * SR + hum(0.006),
                        pan=0.05)
                for h in range(8):
                    pos = h * 0.5 + (swing if h % 2 else 0)
                    v = (0.5 if h % 2 else 0.7) * rng.uniform(0.75, 1.0)
                    add(kit, hat(v, rng), t0 + pos * beat * SR + hum(0.006), pan=0.25)
            # lead: a 2-bar pentatonic motif, repeated with small changes, in B sections and late A
            if name == "B" or (name == "A" and b0 > 16 and rng.random() < 0.5):
                if motif is None:
                    motif = []
                    for slot in sorted(rng.choice(16, size=rng.integers(4, 7), replace=False)):
                        deg_ = PENTATONIC[rng.integers(5)] + 12 * int(rng.integers(0, 2))
                        motif.append((slot * 0.5, deg_, rng.choice([0.5, 1.0, 1.5])))
                half = (bi % 2) * 4
                for pos, d, ln in motif:
                    if half <= pos < half + 4:
                        m = key + 12 + d
                        if rng.random() < 0.15:
                            m += rng.choice([-2, 2, 3])
                        voice_fn = piano(mtof(m + 12), ln * beat * 1.5, 0.4, rng) if style == "piano" else \
                            epiano(mtof(m), ln * beat, 0.32, rng, bright=0.5)
                        add(lead, voice_fn,
                            t0 + (pos - half) * beat * SR + hum(), pan=rng.uniform(-0.15, 0.15))
        b0 += nbars

    # drums and bass ease in and out over about a bar at section changes instead of
    # starting at full level, so nothing jolts a sleeping listener
    groove = np.zeros(length)
    b = 0
    for name, nbars in sections:
        if name in ("A", "B"):
            groove[int(b * bar * SR): int((b + nbars) * bar * SR)] = 1.0
        b += nbars
    ramp = moving_avg(groove, int(bar * SR))
    kit *= ramp[:, None]
    low *= (0.35 + 0.65 * ramp)[:, None]

    # buses: dusty drums, darker keys, gentle sidechain on the keys from the kick
    kit = fft_filter(kit, lo=35, hi=10000)
    keys = fft_filter(keys, lo=170, hi=8000)
    lead = fft_filter(lead, lo=250, hi=7000)
    low = fft_filter(low, hi=350)
    kenv = np.abs(fft_filter(kit[:, 0], hi=8))
    duck = 1 - 0.25 * kenv / (kenv.max() + 1e-9)
    t = np.arange(length) / SR
    trem = 0.12 * np.sin(2 * np.pi * 3.6 * t)
    keys[:, 0] *= (1 + trem) * duck
    keys[:, 1] *= (1 - trem) * duck
    if style == "piano":
        keys[:, 0] /= (1 + trem) * duck
        keys[:, 1] /= (1 - trem) * duck  # piano: no tremolo, no ducking
        mix = 0.9 * keys + 0.55 * low + 0.7 * lead
        mix = reverb(mix, seconds=2.8, wet=0.32, seed=seed)
    elif style == "jazz":
        mix = 0.8 * keys + 0.75 * low + 0.7 * kit + 0.6 * lead
        mix = reverb(mix, seconds=1.8, wet=0.16, seed=seed)
    else:
        mix = 0.8 * keys + 0.6 * low + 0.8 * kit + 0.6 * lead

    # fades: intro rises in, outro falls away
    fin = int(bar * 2 * SR)
    fout_start = int((bars - 4) * bar * SR)
    fade = np.ones(length)
    fade[:fin] = np.linspace(0, 1, fin) ** 2
    fade[fout_start:] = np.linspace(1, 0, length - fout_start) ** 1.5
    mix *= fade[:, None]
    return mix, dict(bpm=round(bpm), key=key, bars=bars, style=style)


def tape(mix, rng):
    """Wow and flutter (slow pitch drift), soft saturation and a gentle top-end roll-off."""
    n = mix.shape[0]
    t = np.arange(n) / SR
    drift = (0.0011 * np.sin(2 * np.pi * 0.45 * t + rng.uniform(0, 6.28))
             + 0.0003 * np.sin(2 * np.pi * 5.8 * t + rng.uniform(0, 6.28)))
    # playback speed = 1 + drift, so the read position is the running sum of (1 + drift)
    pos = np.clip(np.arange(n) + np.cumsum(drift), 0, n - 1)
    out = np.stack([np.interp(pos, np.arange(n), mix[:, c]) for c in (0, 1)], axis=1)
    out = np.tanh(out * 1.3) / 1.3
    return fft_filter(out, hi=11000)


def crackle(n, rng):
    """Vinyl: steady soft hiss plus sparse clicks and the occasional pop."""
    hiss = fft_filter(rng.standard_normal((n, 2)), lo=800, hi=9000) * 0.008
    clicks = np.zeros((n, 2))
    k = int(n / SR * 7)
    pos = rng.integers(0, n, k)
    clicks[pos, rng.integers(0, 2, k)] = rng.pareto(2.5, k) * 0.02 * rng.choice([-1, 1], k)
    clicks = fft_filter(clicks, lo=1200, hi=6000)
    return hiss + np.clip(clicks, -0.06, 0.06)


def moving_avg(x, n):
    """Centred moving average via a running sum: same result as convolving with a box, in O(len(x))."""
    c = np.cumsum(np.concatenate([np.zeros(1), x]))
    i = np.arange(len(x))
    lo, hi = np.clip(i - n // 2, 0, len(x)), np.clip(i - n // 2 + n, 0, len(x))
    return (c[hi] - c[lo]) / (hi - lo)


def write_audio(album, out, bitrate):
    pcm = (album * 32767).astype(np.int16)
    wav = out if out.endswith(".wav") else os.path.splitext(out)[0] + ".tmp.wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    if wav != out:
        import imageio_ffmpeg
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", wav,
                        "-c:a", "aac", "-b:a", bitrate, "-movflags", "+faststart", out], check=True)
        os.remove(wav)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=30, help="exact album length")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--gap", type=float, default=3.0, help="seconds of silence between tracks (music-only mode)")
    ap.add_argument("--bed", help="white-noise bed under the music: rain_road, rain, fan, wind or heater. "
                                  "With a bed the music only plays part of the time (--music-share)")
    ap.add_argument("--music-share", type=float, default=0.35, help="fraction of the album with music, when --bed is set")
    ap.add_argument("--under", help="continuous music with this ambience kept quietly underneath "
                                    "(rain_road, rain, fan, wind, heater); the work/study-music style")
    ap.add_argument("--under-level", type=float, default=0.03, help="loudness of the ambience under the music (RMS)")
    ap.add_argument("--style", choices=["lofi", "jazz", "piano"], default="lofi",
                    help="lofi beats, chill jazz (brushes, walking bass) or soft piano / ambient")
    ap.add_argument("--bitrate", default="112k")
    ap.add_argument("--out", default="album.m4a")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    target = int(args.minutes * 60 * SR)
    starts = []

    if args.bed:
        # white noise the whole way through, with a few lo-fi tracks drifting in and out
        import make_ambience
        chunk = make_ambience.render(2, args.bed, seed=args.seed, seamless=True)
        reps = -(-target // chunk.shape[0])
        album = np.tile(chunk, (reps, 1))[:target]  # the chunk is seamless, so tiling has no seams
        n_tracks = max(1, round(args.music_share * args.minutes / 3.3))
        tracks = []
        for i in range(n_tracks):
            mix, info = compose_track(args.seed * 1000 + i, int(rng.integers(13, 17)) * 4, args.style)
            mix = tape(mix, rng)
            mix *= 0.075 / (np.sqrt((mix[mix.shape[0] // 4: 3 * mix.shape[0] // 4] ** 2).mean()) + 1e-12)
            tracks.append(mix)
            print(f"  track {i + 1}: {info['bars']} bars, {info['bpm']} bpm, key {info['key']}, {mix.shape[0] / SR / 60:.1f} min")
        gap = (target - sum(t.shape[0] for t in tracks)) // len(tracks)
        if gap < 30 * SR:
            raise SystemExit("not enough room for the music; lower --music-share or raise --minutes")
        duck = np.ones(target)
        p = gap // 2  # half a gap at each end, so the album loops into a full gap
        for tr in tracks:
            starts.append(round(p / SR, 2))
            album[p:p + tr.shape[0]] += tr
            # dip the noise by up to 35% while the music plays, following the track's own loudness
            env = np.sqrt(moving_avg(tr.mean(1) ** 2, SR))
            duck[p:p + tr.shape[0]] -= 0.35 * env / (env.max() + 1e-12)
            p += tr.shape[0] + gap
        album *= moving_avg(duck, SR)[:, None]
        album = 0.9 * np.tanh(album / 0.9)
        print(f"mix: {args.bed} bed, {len(tracks)} tracks, {sum(t.shape[0] for t in tracks) / target * 100:.0f}% music, "
              f"{gap / SR / 60:.1f} min of white noise between tracks")
    else:
        tracks, used, i = [], 0, 0
        while True:
            bar_s = 240 / {"lofi": 74, "jazz": 68, "piano": 59}[args.style]  # slow end of each style's tempo
            remaining = (target - used) / SR - args.gap
            if remaining < 70:
                break
            bars = int(rng.integers(13, 17)) * 4 if remaining > 4.2 * 60 else max(16, int(remaining / bar_s) // 4 * 4 - 4)
            mix, info = compose_track(args.seed * 1000 + i, bars, args.style)
            while used + mix.shape[0] + int(args.gap * SR) > target and bars > 16:
                bars -= 8  # too long for the space left: try a shorter arrangement
                mix, info = compose_track(args.seed * 1000 + i, bars, args.style)
            mix = tape(mix, rng)
            if used + mix.shape[0] + int(args.gap * SR) > target:
                break
            tracks.append(mix)
            used += mix.shape[0] + int(args.gap * SR)
            print(f"  track {i + 1}: {info['bars']} bars, {info['bpm']} bpm, key {info['key']}, {mix.shape[0] / SR / 60:.1f} min")
            i += 1
        # spread the leftover time evenly across the gaps so the album is exactly --minutes long
        extra = target - sum(t.shape[0] for t in tracks)
        gaps = [extra // len(tracks)] * len(tracks)
        gaps[-1] += extra - sum(gaps)
        album = np.zeros((target, 2))
        p = 0
        for tr, g in zip(tracks, gaps):
            starts.append(round(p / SR, 2))
            album[p:p + tr.shape[0]] += tr
            p += tr.shape[0] + g
        # no crackle, hiss or any noise under the music: the channel keeps music and white noise apart
        album *= 0.08 / (np.sqrt((album ** 2).mean()) + 1e-12)  # same average loudness every album
        if args.under:
            import make_ambience
            chunk = make_ambience.render(2, args.under, seed=args.seed, seamless=True)
            reps = -(-target // chunk.shape[0])
            bed = np.tile(chunk, (reps, 1))[:target]
            album += bed * (args.under_level / (np.sqrt((bed ** 2).mean()) + 1e-12))
        album = 0.9 * np.tanh(album / 0.9)
        print(f"album: {len(tracks)} tracks, {target / SR / 60:.2f} min, gaps {np.mean(gaps) / SR:.1f} s")

    write_audio(album, args.out, args.bitrate)
    with open(os.path.splitext(args.out)[0] + ".tracks.json", "w") as f:
        json.dump(dict(minutes=args.minutes, bed=args.bed, track_starts=starts), f)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
