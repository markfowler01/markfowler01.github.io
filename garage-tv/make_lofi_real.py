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

--style picks the sound: lofi (the above), garage (future garage / chillstep: warm synth pads,
sub bass and a soft synth pluck from synths.py over the real kit) or house (lo-fi house: Rhodes
chord stabs, sub bass, a soft four-on-the-floor).

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
import synths  # noqa: E402
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
        # a dusty break: muted kick, a muted snare cut short, soft hats and a shaker standing in for
        # brushes (the kit has none). Gains are peak levels relative to the kick.
        self.kick = ins.DrumFolder(kit, "Samples/lofi/kick", "*kick_snoff*", gain=1.0)
        self.snare = ins.DrumFolder(kit, "Samples/lofi/snare", "*snare_muted*", gain=0.75, length=0.25)
        self.hat = ins.DrumFolder(kit, "Samples/lofi/hh", "*hh_closed*", gain=0.35)
        self.hat_open = ins.DrumFolder(kit, "Samples/lofi/hh", "*hh_half*", gain=0.3)
        self.shaker = ins.DrumFolder(kit, "Samples/perc/close/shaker", "*", gain=0.22, length=0.2)
        # the electronic styles want a crisper backbeat: the centre-hit snare, cut short
        self.snap = ins.DrumFolder(kit, "Samples/lofi/snare", "*snare_center*", gain=0.7, length=0.18)
        self.hat_soft = ins.DrumFolder(kit, "Samples/lofi/hh", "*hh_closed*", gain=0.2)


# Per style: tempo range; swing unit in beats (1 swings the 8ths, 0.5 the 16ths) and how late its
# offbeat lands, as a fraction of the unit; and how many bars each chord lasts.
STYLES = {
    "lofi": dict(bpm=(72, 84), unit=1.0, swing=(0.06, 0.10), hr=1),
    # future garage / chillstep: 136-150 bpm with the snare on beat 3, so it feels like 68-75
    "garage": dict(bpm=(136, 150), unit=0.5, swing=(0.08, 0.13), hr=2),
    "house": dict(bpm=(118, 124), unit=0.5, swing=(0.03, 0.06), hr=2),
}
# 16th-note steps in a bar
GARAGE_DRUMS = [
    dict(kick=[0, 10], snare=[8], hat=[2, 6, 10, 14]),
    dict(kick=[0, 7, 10], snare=[8], hat=[2, 6, 10, 14]),
    dict(kick=[0, 10, 13], snare=[4, 12], hat=[2, 6, 10, 14]),  # 2-step
    dict(kick=[0, 6, 10], snare=[4, 12], hat=[2, 6, 10, 14]),
]
HOUSE_DRUMS = [dict(kick=[0, 4, 8, 12], snare=[4, 12], hat=[2, 6, 10, 14])]
# lo-fi house chord stabs: (beat, length in beats, loudness)
HOUSE_STABS = [
    [(0.5, 0.4, 1.0), (1.5, 0.4, 0.85), (2.5, 0.4, 0.9), (3.5, 0.4, 0.8)],
    [(0, 0.9, 1.0), (1.75, 0.4, 0.8), (2.5, 1.2, 0.9)],
    [(0.5, 0.6, 1.0), (2.0, 0.4, 0.8), (2.75, 0.9, 0.9)],
]


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


class Synth:
    """A synth voice with the same play() call as the sample instruments."""

    def __init__(self, fn, shift=0):
        self.fn, self.shift = fn, shift

    def play(self, m, vel, seconds, rng):
        return self.fn(m + self.shift, seconds, vel, rng)


PAD, PLUCK, SUB = Synth(synths.pad), Synth(synths.pluck), Synth(synths.sub)


def compose(band, seed, bars, style="lofi"):
    """One song. style: lofi (lo-fi hip hop on real instruments), garage (future garage /
    chillstep: warm synth pads, sub bass, a soft pluck melody with echoes, shuffled half-time
    drums) or house (lo-fi house: Rhodes chord stabs over a soft four-on-the-floor)."""
    st = STYLES[style]
    rng = np.random.default_rng(seed)
    bpm = rng.uniform(*st["bpm"])
    beat = 60.0 / bpm
    bar = 4 * beat
    hr, unit = st["hr"], st["unit"]
    key = int(rng.choice([57, 58, 60, 62, 63, 65]))
    progA = PROGRESSIONS[rng.integers(len(PROGRESSIONS))]
    progB = PROGRESSIONS[rng.integers(len(PROGRESSIONS))]
    grooves = {"lofi": DRUM_PATTERNS, "garage": GARAGE_DRUMS, "house": HOUSE_DRUMS}[style]
    groove = grooves[rng.integers(len(grooves))]
    swing = rng.uniform(*st["swing"])
    compA, compB = (COMP_PATTERNS[i] for i in rng.choice(len(COMP_PATTERNS), 2, replace=False))
    stabA, stabB = (HOUSE_STABS[i] for i in rng.choice(len(HOUSE_STABS), 2, replace=False))
    keys_inst = band.rhodes  # warm Rhodes carries the lo-fi and house songs
    lead_inst = PLUCK if style == "garage" else band.guitar if rng.random() < 0.6 else band.piano
    rhythm = melody_rhythm(rng)

    length = int((bars * bar + 4.0) * SR)
    keys, pads, low, kik, kit, snr, lead = (np.zeros((length, 2), np.float32) for _ in range(7))

    def hum(sec=0.006):
        return rng.normal(0, sec) * SR

    def at(t0, pos):
        """Sample position of beat `pos` in the bar starting at t0, on the song's swing grid:
        the offbeat in every `unit` of beats is late by `swing` of a unit and the notes around
        it move in proportion, so drums, bass, keys and melody all share one feel."""
        whole, frac = divmod(pos / unit, 1.0)
        mid = 0.5 + swing
        frac = frac * mid / 0.5 if frac < 0.5 else mid + (frac - 0.5) * (1 - mid) / 0.5
        return t0 + (whole + frac) * unit * beat * SR

    def chord(prog, i):
        deg, q = prog[i % 4]
        return key + deg, q

    def low_note(r):
        return r - 24 if r - 24 >= 31 else r - 12

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
            ci, new_chord = bi // hr, bi % hr == 0
            t0 = bi * bar * SR
            root, q = chord(prog, ci)
            notes = voice(root, q, center)
            center = int(np.clip(np.mean(notes), 58, 66))
            bm, nb = low_note(root), low_note(chord(prog, ci + 1)[0])
            # keys and pads
            if style == "lofi":
                soft = 0.42 if not busy else 0.55
                comp = [(0, 3.8, 1.0, False)] if not busy else (compB if name == "B" else compA)
                for pos, ln, v, push in comp:
                    if push and k == nbars - 1 and last:
                        continue
                    ch = voice(*chord(prog, ci + 1), center) if push else notes
                    for j, m in enumerate(ch):  # a slight roll, low note first, like real hands
                        put(keys, keys_inst.play(m, soft * v * rng.uniform(0.85, 1.0), ln * beat, rng),
                            at(t0, pos) + j * rng.uniform(0.006, 0.018) * SR + hum(), pan=(m - 62) / 30)
            else:
                if new_chord:  # a warm pad holds each chord (quietly under the house Rhodes)
                    pv = (0.5 if busy else 0.42) if style == "garage" else 0.3
                    for m in notes:
                        put(pads, PAD.play(m, hr * bar - 0.05, pv * rng.uniform(0.9, 1.0), rng),
                            t0 + hum(0.01), pan=(m - 62) / 40)
                if style == "house":
                    stabs = [(0, 3.8, 1.0)] if not busy else (stabB if name == "B" else stabA)
                    for pos, ln, v in stabs:
                        for j, m in enumerate(notes):
                            put(keys, keys_inst.play(m, 0.5 * v * rng.uniform(0.85, 1.0), ln * beat, rng),
                                at(t0, pos) + j * 0.004 * SR + hum(0.003), pan=(m - 62) / 30)
            # bass
            if name not in ("intro", "outro"):
                if style == "lofi":  # sparse, round: root on 1, sometimes a passing note on 4
                    put(low, band.bass.play(bm, 0.8, beat * 2.6, rng), t0 + hum(0.004))
                    if rng.random() < 0.3:
                        put(low, band.bass.play(int(rng.choice([bm + 7, nb - 1, nb + 2])), 0.6, beat * 0.8, rng),
                            at(t0, 3) + hum(0.004))
                elif style == "garage":  # sub notes locked to the kick
                    ks = groove["kick"] + [16]
                    for s, e in zip(ks, ks[1:]):
                        put(low, SUB.play(bm, (e - s) * 0.25 * beat * 0.9, 0.8, rng), at(t0, s * 0.25))
                else:  # house: bass on the offbeats, jumping an octave now and then
                    for s in (2, 6, 10, 14):
                        m = bm + 12 if s == 14 and rng.random() < 0.4 else bm
                        put(low, SUB.play(m, 0.35 * beat, 0.75, rng), at(t0, s * 0.25))
            # drums
            if busy:
                fill = k == nbars - 1 and not last
                if style == "lofi":
                    for b in groove["kick"]:
                        put(kik, band.kick.play(0.92 * rng.uniform(0.92, 1.0), rng), at(t0, b) + hum(0.002))
                    # snare lands exactly with the hi-hat on 2 and 4 (any lag between them sounds like a flam)
                    for b in groove["snare"]:
                        put(snr, band.snare.play(0.6 * rng.uniform(0.9, 1.0), rng), at(t0, b) + hum(0.001), pan=0.05)
                    for g in range(16):
                        if g % 4 and g % 2 and rng.random() < 0.04:
                            put(snr, band.snare.play(0.15, rng), at(t0, g * 0.25) + hum(0.001), pan=0.05)
                    for h in range(8):  # brush-like swish on the offbeats
                        if h % 2:
                            put(kit, band.shaker.play(0.6 * rng.uniform(0.8, 1.0), rng), at(t0, h * 0.5) + hum(0.002),
                                pan=-0.25)
                    if fill:
                        for i, pos in enumerate((3.25, 3.5, 3.75)):
                            put(snr, band.snare.play(0.25 + 0.08 * i, rng), at(t0, pos) + hum(0.001), pan=0.05)
                    for h in range(8):
                        pos = h * 0.5
                        if fill and pos > 3.2:
                            continue
                        opn = h == 7 and k % 8 == 7 and not fill
                        v = (0.45 if h % 2 else 0.6) * (1.15 if h % 4 == 0 else 1.0) * rng.uniform(0.8, 1.0)
                        put(kit, (band.hat_open if opn else band.hat).play(v, rng), at(t0, pos) + hum(0.003), pan=0.3)
                else:  # garage and house: 16th-note grid
                    for s in groove["kick"]:
                        put(kik, band.kick.play(0.92 * rng.uniform(0.92, 1.0), rng), at(t0, s * 0.25) + hum(0.002))
                    for s in groove["snare"]:
                        put(snr, band.snap.play(0.7 * rng.uniform(0.9, 1.0), rng), at(t0, s * 0.25) + hum(0.001),
                            pan=0.05)
                    if style == "garage":
                        for s in (7, 15):  # ghost notes push the shuffle
                            if rng.random() < 0.25:
                                put(snr, band.snap.play(0.2, rng), at(t0, s * 0.25) + hum(0.001), pan=0.05)
                    hat = band.hat_open if style == "house" else band.hat
                    for s in groove["hat"]:
                        if fill and s > 12:
                            continue
                        put(kit, hat.play(0.55 * rng.uniform(0.85, 1.0), rng), at(t0, s * 0.25) + hum(0.002), pan=0.3)
                    for s in range(16):  # soft shuffled 16ths
                        if s % 2:
                            tick = band.shaker if style == "garage" else band.hat_soft
                            put(kit, tick.play(0.5 * rng.uniform(0.7, 1.0), rng), at(t0, s * 0.25) + hum(0.002),
                                pan=-0.25)
                    if fill:
                        for i, s in enumerate((13, 14, 15)):
                            put(snr, band.snap.play(0.3 + 0.1 * i, rng), at(t0, s * 0.25) + hum(0.001), pan=0.05)
            # lead: a question and answer (4 chords long) that follows the chords
            span = 4 * hr
            if lead_on and k % span == 0 and nbars - k >= span:
                tk = (name, (k // span) % 2)
                if tk not in tunes:
                    c = [chord(prog, ci + i) for i in range(4)]
                    call = melody_pitches(rhythm, c[:2], prev, key + 12, rng)
                    tunes[tk] = (call, melody_pitches(rhythm, c[2:], call[-1], key + 12, rng, cadence=True))
                for half, pitches in enumerate(tunes[tk]):
                    for (pos, ln), m in zip(rhythm, pitches):
                        if rng.random() < 0.12:
                            continue
                        put(lead, lead_inst.play(m, 0.5 * rng.uniform(0.85, 1.0), ln * beat * hr, rng),
                            at(t0, (half * 8 + pos) * hr) + hum(), pan=rng.uniform(-0.2, 0.2))
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
    # pump: keys, pads (and in house the bass) duck under each kick
    kenv = fft_filter(np.abs(kik[:, 0]), hi=6)
    kenv = np.clip(kenv / (np.abs(kenv).max() + 1e-9), 0, 1)
    depth = {"lofi": 0.2, "garage": 0.3, "house": 0.4}[style]
    duck = (1 - depth * kenv)[:, None]
    snare_hi = 5000 if style == "lofi" else 7000  # lo-fi: darker snare, like an old record
    kit += kik + fft_filter(snr, lo=150, hi=snare_hi)
    kit *= ramp[:, None]
    low *= (0.4 + 0.6 * ramp)[:, None]

    # The keys open filtered (muffled) and brighten as the drums come in.
    first = sections[0][1] if sections[0][0] == "intro" else 2
    opened = np.clip((np.arange(length) / SR / bar - 0.5) / max(first, 1), 0, 1) ** 1.5
    keys = (fft_filter(keys, lo=140, hi=900) * (1 - opened[:, None])
            + fft_filter(keys, lo=140, hi=6000 if style == "lofi" else 5000) * opened[:, None])
    keys = reverb(keys * duck, seconds=1.6, wet=0.16, seed=seed + 3)
    pads = reverb(fft_filter(pads, lo=120, hi=2200 if style == "garage" else 1600) * duck,
                  seconds=3.5, wet=0.35, seed=seed + 5)
    if style == "garage":
        lead = synths.echo(lead, 0.75 * beat)  # dotted-8th echoes bouncing side to side
        lead = reverb(fft_filter(lead, lo=250, hi=6000), seconds=2.6, wet=0.3, seed=seed + 4)
        low = fft_filter(low, lo=30, hi=500)
        kit = reverb(fft_filter(kit, lo=30, hi=9000), seconds=1.2, wet=0.2, seed=seed + 1)
    else:
        lead = reverb(fft_filter(lead, lo=200, hi=6500), seconds=1.8, wet=0.22, seed=seed + 4)
        low = fft_filter(low, lo=35, hi=1200 if style == "lofi" else 600)
        if style == "house":
            low = low * (1 - 0.3 * kenv)[:, None]
        kit = reverb(fft_filter(kit, lo=30, hi=7000 if style == "lofi" else 8000), seconds=0.6, wet=0.12,
                     seed=seed + 1)
    level = lambda x: x / (np.sqrt((x ** 2).mean()) + 1e-9)  # noqa: E731
    weights = {"lofi": (1.0, 0.0, 0.75, 0.7, 0.32), "garage": (0.0, 1.0, 0.8, 0.75, 0.45),
               "house": (1.0, 0.4, 0.75, 0.8, 0.3)}[style]  # keys, pads, bass, drums, lead
    mix = sum(w * level(x) for w, x in zip(weights, (keys, pads, low, kit, lead)) if w)
    mix = glue(mix / 4)
    fin, fout = int(bar * 2 * SR), int((bars - 4) * bar * SR)
    fade = np.ones(length)
    fade[:fin] = np.linspace(0, 1, fin) ** 2
    fade[fout:] = np.linspace(1, 0, length - fout) ** 1.5
    mix *= fade[:, None]
    lead_name = "pluck" if lead_inst is PLUCK else "guitar" if lead_inst is band.guitar else "piano"
    return mix, dict(style=style, bpm=round(bpm), key=key, bars=bars,
                     keys="pads" if style == "garage" else "rhodes", lead=lead_name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=35)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--gap", type=float, default=3.0, help="seconds of silence between songs")
    ap.add_argument("--bitrate", default="192k")
    ap.add_argument("--out", default="music.m4a")
    ap.add_argument("--style", choices=sorted(STYLES), default="lofi")
    args = ap.parse_args()
    bar_s = 240 / np.mean(STYLES[args.style]["bpm"])
    rng = np.random.default_rng(args.seed)
    band = Band()
    target = int(args.minutes * 60 * SR)
    tracks, used, i = [], 0, 0
    while True:
        remaining = (target - used) / SR - args.gap
        if remaining < 70:
            break
        secs = rng.uniform(160, 200) if remaining > 4.4 * 60 else remaining - 10
        bars = max(16, int(secs / bar_s) // 4 * 4)
        mix, info = compose(band, args.seed * 1000 + i, bars, args.style)
        while used + len(mix) + int(args.gap * SR) > target and bars > 16:
            bars -= 8
            mix, info = compose(band, args.seed * 1000 + i, bars, args.style)
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
