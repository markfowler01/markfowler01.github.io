#!/usr/bin/env python3
"""Lo-fi beats played on real recorded instruments: new songs every time, free to use.

The songwriting is generated (chords, comping rhythm, bass line, drum groove, a melody that
follows the chords); every note is played on a real recording from free sample libraries
(github.com/sfzinstruments), each cleared for commercial use:

  keys   : 1977 Rhodes Mark I (jlearman.jRhodes3d; free to use in your own music) or a grand
           piano (Osiris Piano, CC0)
  bass   : upright bass played softly with the fingers (Karoryfer Sneakybass, CC0)
  drums  : a real kit through a lo-fi mic chain (Virtuosity Drums, lofi mics, CC0)
  lead   : clean electric guitar (Karoryfer Emily guitar, CC0) or the piano

Music only: no hiss, crackle, rain or noise is added. The album is exactly --minutes long
and loops under the video; a .tracks.json lists where each song starts.

  python3 make_lofi_real.py --minutes 35 --seed 7 --out music.m4a
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import instruments as ins  # noqa: E402
from make_lofi import (PROGRESSIONS, QUALITY, DRUM_PATTERNS, SR, add, arrangement, fft_filter,  # noqa: E402
                       moving_avg, reverb, tape, voice, write_audio)

SCALE = [0, 2, 4, 5, 7, 9, 11]
# keys comping per bar: (beat, length in beats, loudness, push). A push plays the next chord
# early, on the "and" of 4, the way a player anticipates the change.
COMP_PATTERNS = [
    [(0, 3.8, 1.0, False)],
    [(0, 1.4, 1.0, False), (1.5, 2.3, 0.75, False)],
    [(0, 0.9, 1.0, False), (2.5, 1.3, 0.8, False)],
    [(0, 2.4, 1.0, False), (3.5, 0.5, 0.8, True)],
    [(0.5, 1.5, 0.9, False), (2.5, 1.0, 0.75, False), (3.5, 0.5, 0.7, True)],
]


class Band:
    """The instruments, loaded once and shared by every song on the album."""

    def __init__(self):
        rhodes_sfz = ins.find_file("jlearman.jRhodes3d", "*mono*.sfz")
        self.rhodes = ins.SfzInstrument("jlearman.jRhodes3d", rhodes_sfz, release=0.35, gain=0.9)
        self.piano = ins.NoteFolder("Osiris_Piano", "UC/A", r"_(?P<note>[A-G][b#]?-?\d)_vl(?P<vl>\d)\.", gain=1.0,
                                    release=0.4, max_len=7)
        self.bass = ins.NoteFolder("karoryfer.sneakybass", "Samples/finger",
                                   r"sneakybass_(?P<note>[a-g][b#]?\d)_finger_rr(?P<rr>\d)", gain=1.2, release=0.12)
        self.guitar = ins.NoteFolder("karoryfer.emilyguitar", "notes",
                                     r"^(?P<note>[a-g][b#]?\d)_(?P<vl>p|mp|mf|f)_rr(?P<rr>\d)",
                                     vl_order=["p", "mp", "mf", "f"], gain=0.8, release=0.2, max_len=4)
        kit = "virtuosity_drums"
        self.kick = ins.DrumFolder(kit, "Samples/lofi/kick", "*kick_snoff*", gain=1.0)
        self.snare = ins.DrumFolder(kit, "Samples/lofi/snare", "*snare_center*", gain=0.8)
        self.rim = ins.DrumFolder(kit, "Samples/lofi/snare", "*snare_crossstick*", gain=0.7)
        self.hat = ins.DrumFolder(kit, "Samples/lofi/hh", "*hh_closed*", gain=0.55)
        self.hat_open = ins.DrumFolder(kit, "Samples/lofi/hh", "*hh_half*", gain=0.45)


def put(buf, sig, start, pan=0.0):
    """Mix a stereo note into the buffer with a gentle pan (constant power)."""
    s = int(start)
    if s < 0:  # a humanised note that lands just before the song starts
        sig, s = sig[-s:], 0
    if s >= len(buf) or len(sig) == 0:
        return
    e = min(len(buf), s + len(sig))
    a = (pan + 1) * np.pi / 4
    buf[s:e, 0] += sig[:e - s, 0] * np.cos(a) * 1.414
    buf[s:e, 1] += sig[:e - s, 1] * np.sin(a) * 1.414


def melody_rhythm(rng):
    grid = np.arange(0, 7.5, 0.5)
    weight = np.where(grid % 1 == 0, 1.0, 0.45)
    on = sorted(rng.choice(grid, size=int(rng.integers(4, 7)), replace=False, p=weight / weight.sum()))
    out = []
    for i, pos in enumerate(on):
        nxt = on[i + 1] if i + 1 < len(on) else 8.0
        out.append((float(pos), float(min(nxt - pos, 2.0 if i == len(on) - 1 else 1.5) * 0.92)))
    return out


def melody_pitches(rhythm, chords, prev, key, rng, cadence=False):
    pool = [key + d + 12 * o for o in (0, 1, 2) for d in SCALE if key + 9 <= key + d + 12 * o <= key + 26]
    out = []
    for i, (pos, _) in enumerate(rhythm):
        root, q = chords[min(int(pos // 4), len(chords) - 1)]
        tones = {(root + iv) % 12 for iv in QUALITY[q]}
        if cadence and i == len(rhythm) - 1:
            cand = [m for m in pool if (m - key) % 12 in (0, 4)]
        elif pos % 2 == 0:
            cand = [m for m in pool if m % 12 in tones]
        else:
            j = min(range(len(pool)), key=lambda j: abs(pool[j] - prev))
            step = int(rng.choice([-2, -1, 1, 2], p=[0.15, 0.35, 0.35, 0.15]))
            cand = [pool[int(np.clip(j + step, 0, len(pool) - 1))]]
        prev = min(cand, key=lambda m: abs(m - (prev + rng.normal(0, 2.5))))
        out.append(prev)
    return out


def glue(x, threshold=0.25, ratio=2.5, window=0.08):
    env = np.sqrt(moving_avg((x ** 2).mean(axis=1), int(window * SR))) + 1e-9
    gain = np.where(env > threshold, (env / threshold) ** (1 / ratio - 1), 1.0)
    return x * moving_avg(gain, int(0.05 * SR))[:, None]


def compose(band, seed, bars):
    rng = np.random.default_rng(seed)
    bpm = rng.uniform(70, 84)
    beat = 60.0 / bpm
    bar = 4 * beat
    key = int(rng.choice([57, 58, 60, 62, 63, 65]))
    progA = PROGRESSIONS[rng.integers(len(PROGRESSIONS))]
    progB = PROGRESSIONS[rng.integers(len(PROGRESSIONS))]
    groove = DRUM_PATTERNS[rng.integers(len(DRUM_PATTERNS))]
    swing = rng.uniform(0.08, 0.14)
    compA, compB = (COMP_PATTERNS[i] for i in rng.choice(len(COMP_PATTERNS), 2, replace=False))
    keys_inst = band.rhodes if rng.random() < 0.7 else band.piano
    lead_inst = band.guitar if (keys_inst is band.piano or rng.random() < 0.6) else band.piano
    rhythm = melody_rhythm(rng)

    length = int((bars * bar + 4.0) * SR)
    keys, low, kit, lead = (np.zeros((length, 2), np.float32) for _ in range(4))

    def hum(sec=0.006):
        return rng.normal(0, sec) * SR

    def at(t0, pos):
        """Sample position of beat `pos` in the bar starting at t0, on the song's swing grid:
        every offbeat 8th is late by `swing` beats and the 16ths around it move in proportion,
        so drums, bass, keys and melody all share one feel."""
        whole, frac = divmod(pos, 1.0)
        mid = 0.5 + swing
        frac = frac * mid / 0.5 if frac < 0.5 else mid + (frac - 0.5) * (1 - mid) / 0.5
        return t0 + (whole + frac) * beat * SR

    def chord(prog, i):
        deg, q = prog[i % 4]
        return key + deg, q

    sections = arrangement(bars, rng)
    tunes = {}
    b0, center, prev = 0, 62, key + 16
    for si, (name, nbars) in enumerate(sections):
        prog = progB if name == "B" else progA
        busy = name in ("A", "B")
        lead_on = name == "B" or (name == "A" and b0 > 16 and rng.random() < 0.6)
        last = si == len(sections) - 1
        for k in range(nbars):
            bi = b0 + k
            t0 = bi * bar * SR
            root, q = chord(prog, bi)
            notes = voice(root, q, center)
            center = int(np.clip(np.mean(notes), 58, 66))
            soft = 0.42 if not busy else 0.55
            comp = [(0, 3.8, 1.0, False)] if not busy else (compB if name == "B" else compA)
            for pos, ln, v, push in comp:
                if push and k == nbars - 1 and last:
                    continue
                ch = voice(*chord(prog, bi + 1), center) if push else notes
                for j, m in enumerate(ch):  # a slight roll, low note first, like real hands
                    put(keys, keys_inst.play(m, soft * v * rng.uniform(0.85, 1.0), ln * beat, rng),
                        at(t0, pos) + j * rng.uniform(0.006, 0.018) * SR + hum(), pan=(m - 62) / 30)
            # bass: root on 1, a passing note into the next chord on 4
            bm = root - 24 if root - 24 >= 31 else root - 12
            nroot = chord(prog, bi + 1)[0]
            nb = nroot - 24 if nroot - 24 >= 31 else nroot - 12
            if name not in ("intro", "outro"):
                put(low, band.bass.play(bm, 0.8, beat * 1.7, rng), t0 + hum(0.004))
                if rng.random() < 0.6:
                    put(low, band.bass.play(int(rng.choice([bm + 7, nb - 1, nb + 2])), 0.6, beat * 0.8, rng),
                        at(t0, 3) + hum(0.004))
            # drums
            if busy:
                fill = k == nbars - 1 and not last
                for b in groove["kick"]:
                    put(kit, band.kick.play(0.75 * rng.uniform(0.85, 1.0), rng), at(t0, b) + hum(0.003))
                for b in groove["snare"]:
                    hit = band.rim if (name == "A" and b0 < 12) else band.snare  # cross-stick early on
                    put(kit, hit.play(0.6 * rng.uniform(0.85, 1.0), rng), at(t0, b) + 0.008 * SR + hum(0.003), pan=0.05)
                for g in range(16):
                    if g % 4 and rng.random() < 0.06:
                        put(kit, band.snare.play(0.15, rng), at(t0, g * 0.25) + hum(0.003), pan=0.05)
                if fill:
                    for i, pos in enumerate((3.25, 3.5, 3.75)):
                        put(kit, band.snare.play(0.25 + 0.1 * i, rng), at(t0, pos) + hum(0.002), pan=0.05)
                for h in range(8):
                    pos = h * 0.5
                    if fill and pos > 3.2:
                        continue
                    opn = h == 7 and k % 8 == 7 and not fill
                    v = (0.45 if h % 2 else 0.6) * (1.15 if h % 4 == 0 else 1.0) * rng.uniform(0.8, 1.0)
                    put(kit, (band.hat_open if opn else band.hat).play(v, rng), at(t0, pos) + hum(0.003), pan=0.3)
            # lead: a 4-bar question and answer that follows the chords
            if lead_on and k % 4 == 0 and nbars - k >= 4:
                tk = (name, (k // 4) % 2)
                if tk not in tunes:
                    c = [chord(prog, bi + i) for i in range(4)]
                    call = melody_pitches(rhythm, c[:2], prev, key + 12, rng)
                    tunes[tk] = (call, melody_pitches(rhythm, c[2:], call[-1], key + 12, rng, cadence=True))
                for half, pitches in enumerate(tunes[tk]):
                    for (pos, ln), m in zip(rhythm, pitches):
                        if rng.random() < 0.12:
                            continue
                        put(lead, lead_inst.play(m, 0.5 * rng.uniform(0.85, 1.0), ln * beat, rng),
                            at(t0, half * 8 + pos) + hum(), pan=rng.uniform(-0.2, 0.2))
                        prev = m
        b0 += nbars

    # drums and bass ease in and out at section changes
    on = np.zeros(length)
    b = 0
    for name, nbars in sections:
        if name in ("A", "B"):
            on[int(b * bar * SR): int((b + nbars) * bar * SR)] = 1.0
        b += nbars
    ramp = moving_avg(on, int(bar * SR))
    kit *= ramp[:, None]
    low *= (0.4 + 0.6 * ramp)[:, None]

    # mix: warm keys with a soft sidechain from the kick, round bass, dusty drums in a small room
    keys = fft_filter(keys, lo=140, hi=7500)
    lead = reverb(fft_filter(lead, lo=200, hi=8000), seconds=1.8, wet=0.2, seed=seed + 4)
    low = fft_filter(low, lo=35, hi=2500)
    kit = reverb(fft_filter(kit, lo=30, hi=12000), seconds=0.6, wet=0.1, seed=seed + 1)
    kenv = np.abs(fft_filter(kit[:, 0], hi=8))
    duck = (1 - 0.2 * kenv / (kenv.max() + 1e-9))[:, None]
    keys = reverb(keys * duck, seconds=1.6, wet=0.16, seed=seed + 3)
    level = lambda x: x / (np.sqrt((x ** 2).mean()) + 1e-9)  # noqa: E731
    mix = 0.95 * level(keys) + 0.75 * level(low) + 0.8 * level(kit) + 0.45 * level(lead)
    mix = glue(mix / 4)
    fin, fout = int(bar * 2 * SR), int((bars - 4) * bar * SR)
    fade = np.ones(length)
    fade[:fin] = np.linspace(0, 1, fin) ** 2
    fade[fout:] = np.linspace(1, 0, length - fout) ** 1.5
    mix *= fade[:, None]
    name = "rhodes" if keys_inst is band.rhodes else "piano"
    return mix, dict(bpm=round(bpm), key=key, bars=bars, keys=name, lead="guitar" if lead_inst is band.guitar else "piano")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=35)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--gap", type=float, default=3.0, help="seconds of silence between songs")
    ap.add_argument("--bitrate", default="192k")
    ap.add_argument("--out", default="music.m4a")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    band = Band()
    target = int(args.minutes * 60 * SR)
    tracks, used, i = [], 0, 0
    while True:
        remaining = (target - used) / SR - args.gap
        if remaining < 70:
            break
        bars = int(rng.integers(13, 17)) * 4 if remaining > 4.4 * 60 else max(16, int(remaining / 3.4) // 4 * 4 - 4)
        mix, info = compose(band, args.seed * 1000 + i, bars)
        while used + len(mix) + int(args.gap * SR) > target and bars > 16:
            bars -= 8
            mix, info = compose(band, args.seed * 1000 + i, bars)
        if used + len(mix) + int(args.gap * SR) > target:
            break
        tracks.append(tape(mix, rng))
        used += len(mix) + int(args.gap * SR)
        print(f"  song {i + 1}: {info}  {len(mix) / SR / 60:.1f} min", flush=True)
        i += 1
    extra = target - sum(len(t) for t in tracks)
    gaps = [extra // len(tracks)] * len(tracks)
    gaps[-1] += extra - sum(gaps)
    album = np.zeros((target, 2))
    starts, p = [], 0
    for tr, g in zip(tracks, gaps):
        starts.append(round(p / SR, 2))
        album[p:p + len(tr)] += tr
        p += len(tr) + g
    album *= 0.08 / (np.sqrt((album ** 2).mean()) + 1e-12)
    album = 0.9 * np.tanh(album / 0.9)  # music only: nothing else is mixed in
    write_audio(album, args.out, args.bitrate)
    with open(os.path.splitext(args.out)[0] + ".tracks.json", "w") as f:
        json.dump(dict(minutes=args.minutes, track_starts=starts), f)
    if ins.lead_trims:
        lt = np.array(ins.lead_trims) * 1000
        print(f"sample starts trimmed: {len(lt)} samples, median {np.median(lt):.1f} ms, max {lt.max():.1f} ms")
    print(f"album: {len(tracks)} songs, {args.minutes:.1f} min -> {args.out}")


if __name__ == "__main__":
    main()
