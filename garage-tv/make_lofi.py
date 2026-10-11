#!/usr/bin/env python3
"""Compose an original, royalty-free lo-fi album for sleep videos.

Every track is generated from scratch (no samples, no borrowed music):
  keys   : FM electric piano playing jazzy 7th/9th chords, softly strummed, with tremolo
  bass   : warm round bass following the chord roots
  drums  : quiet, dusty, swung boom-bap (kick, snare, hats), humanised
  lead   : sparse pentatonic melody on a bell-like piano in some sections
  texture: vinyl crackle and hiss, tape wow and flutter, gentle saturation

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


def compose_track(seed, bars):
    rng = np.random.default_rng(seed)
    bpm = rng.uniform(70, 82)
    beat = 60.0 / bpm
    bar = 4 * beat
    key = int(rng.choice([57, 58, 60, 62, 63, 65]))  # A, Bb, C, D, Eb, F (tonic, MIDI)
    progA = PROGRESSIONS[rng.integers(len(PROGRESSIONS))]
    progB = PROGRESSIONS[rng.integers(len(PROGRESSIONS))]
    drums = DRUM_PATTERNS[rng.integers(len(DRUM_PATTERNS))]
    swing = rng.uniform(0.08, 0.13)  # offbeat 8ths land this many beats late

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
            for j, m in enumerate(notes):
                add(keys, epiano(mtof(m), bar * 0.95, soft * rng.uniform(0.8, 1.0), rng),
                    t0 + j * rng.uniform(0.008, 0.022) * SR + hum(), pan=rng.uniform(-0.35, 0.35))
            if name in ("A", "B") and rng.random() < 0.45:
                at = rng.choice([1.5, 2.0, 2.5])
                for m in notes[1:]:
                    add(keys, epiano(mtof(m), beat * 1.2, 0.35 * rng.uniform(0.8, 1.0), rng, bright=0.7),
                        t0 + at * beat * SR + hum(), pan=rng.uniform(-0.3, 0.3))
            # bass: root on 1, fifth or approach note late in the bar
            if name not in ("intro", "outro"):
                bm = root - 24 if root - 24 >= 33 else root - 12
                add(low, bass_note(mtof(bm), beat * 1.6, 0.85), t0 + hum(0.004))
                if rng.random() < 0.6:
                    nxt = key + prog[(bi + 1) % 4][0]
                    approach = rng.choice([bm + 7, (nxt - 24 if nxt - 24 >= 33 else nxt - 12) - 1])
                    add(low, bass_note(mtof(approach), beat * 0.8, 0.6), t0 + 3 * beat * SR + hum(0.004))
            # drums: swung, quiet, humanised; out for intro / break / outro
            if name in ("A", "B"):
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
                        add(lead, epiano(mtof(m), ln * beat, 0.32, rng, bright=0.5),
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
    mix = 0.8 * keys + 0.6 * low + 0.8 * kit + 0.6 * lead

    # fades: intro rises in, outro falls away
    fin = int(bar * 2 * SR)
    fout_start = int((bars - 4) * bar * SR)
    fade = np.ones(length)
    fade[:fin] = np.linspace(0, 1, fin) ** 2
    fade[fout_start:] = np.linspace(1, 0, length - fout_start) ** 1.5
    mix *= fade[:, None]
    return mix, dict(bpm=round(bpm), key=key, bars=bars)


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
    ap.add_argument("--gap", type=float, default=3.0, help="seconds of crackle between tracks (music-only mode)")
    ap.add_argument("--bed", help="white-noise bed under the music: rain_road, rain, fan, wind or heater. "
                                  "With a bed the music only plays part of the time (--music-share)")
    ap.add_argument("--music-share", type=float, default=0.35, help="fraction of the album with music, when --bed is set")
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
            mix, info = compose_track(args.seed * 1000 + i, int(rng.integers(13, 17)) * 4)
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
            bar_s = 240 / 76
            remaining = (target - used) / SR - args.gap
            if remaining < 70:
                break
            bars = int(rng.integers(13, 17)) * 4 if remaining > 4.2 * 60 else max(16, int(remaining / bar_s) // 4 * 4 - 4)
            mix, info = compose_track(args.seed * 1000 + i, bars)
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
        album += crackle(target, rng)
        album *= 0.08 / (np.sqrt((album ** 2).mean()) + 1e-12)  # same average loudness every album
        album = 0.9 * np.tanh(album / 0.9)
        print(f"album: {len(tracks)} tracks, {target / SR / 60:.2f} min, gaps {np.mean(gaps) / SR:.1f} s")

    write_audio(album, args.out, args.bitrate)
    with open(os.path.splitext(args.out)[0] + ".tracks.json", "w") as f:
        json.dump(dict(minutes=args.minutes, bed=args.bed, track_starts=starts), f)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
