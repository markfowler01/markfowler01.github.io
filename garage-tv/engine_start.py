#!/usr/bin/env python3
"""The sound of the car starting, made from scratch (no recordings, nothing to license): a key click,
the starter cranking, the engine catching with a rev, then settling into a deep V8 idle that fades.

  python3 engine_start.py --out start.wav        # prints when the engine catches (lights come on then)

Used at the start of every Night Studio video: the car sits with its lights off, starts, the lights
come on and the music comes in (Mark, Nov 1).
"""
import argparse
import math
import wave

import numpy as np

SR = 44100
CRANK_AT, CATCH_AT, LENGTH = 0.45, 1.45, 9.0  # seconds into the sound


def lowpass(x, hz):
    a = math.exp(-2 * math.pi * hz / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):  # one-pole filter; the sound is short, so a plain loop is fine
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def burst(rng, ms, decay_ms):
    n = int(ms / 1000 * SR)
    return rng.standard_normal(n) * np.exp(-np.arange(n) / (decay_ms / 1000 * SR))


def render(seed=3):
    rng = np.random.default_rng(seed)
    n = int(LENGTH * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)

    # key: two small clicks
    for at in (0.0, 0.12):
        b = burst(rng, 8, 1.2) * 0.35
        i = int(at * SR)
        out[i:i + len(b)] += b

    # starter: a whining motor that dips each time a cylinder compresses (about 11 a second)
    crank = (t >= CRANK_AT) & (t < CATCH_AT + 0.05)
    chug = 0.5 + 0.5 * np.cos(2 * math.pi * 11 * (t - CRANK_AT))
    whine_f = 310 - 60 * chug
    whine = np.sin(2 * math.pi * np.cumsum(whine_f) / SR) * 0.12
    thump = lowpass(rng.standard_normal(n), 180) * chug ** 3 * 2.2
    out += np.where(crank, whine + thump, 0.0)

    # engine speed: catches, flares to ~3200 rpm, falls back and settles at a lumpy ~850 rpm idle
    rpm = np.zeros(n)
    s = t - CATCH_AT
    rise = np.clip(s / 0.32, 0, 1)
    flare = 300 + 2900 * (1 - (1 - rise) ** 2)
    fall = 850 + (3200 - 850) * np.exp(-np.clip(s - 0.42, 0, None) / 0.38)
    rpm = np.where(s < 0, 0.0, np.where(s < 0.42, flare, fall))
    rpm *= 1 + 0.03 * np.sin(2 * math.pi * 1.7 * t)  # idle hunting
    fire_hz = rpm / 60 * 4  # V8: four firings per turn

    # each firing is a short low exhaust pulse; uneven strengths give the V8 burble
    phase = np.cumsum(fire_hz / SR)
    fires = np.nonzero(np.diff(np.floor(phase)) > 0)[0]
    pulses = np.zeros(n)
    pulses[fires] = rng.uniform(0.6, 1.4, len(fires)) * np.where(np.arange(len(fires)) % 8 < 2, 1.3, 1.0)
    kern = burst(rng, 25, 6)
    exhaust = np.convolve(pulses, kern)[:n]
    exhaust = lowpass(lowpass(exhaust, 900), 900)
    tone = sum(np.sin(2 * math.pi * k * phase / 2) / k for k in (1, 2, 3, 4))  # the engine's note
    load = np.clip(rpm / 3200, 0, 1)
    mech = lowpass(rng.standard_normal(n), 3000) - lowpass(rng.standard_normal(n), 900)
    engine = 2.4 * exhaust + 0.10 * tone * (s >= 0) + 0.04 * mech * load
    out += np.where(s >= 0, engine, 0.0)

    # fade the idle out over the last four seconds, then level it
    fade = np.clip((LENGTH - t) / 4.0, 0, 1)
    out *= fade
    out /= np.abs(out).max() + 1e-9
    out = 0.85 * np.tanh(out * 1.4) / np.tanh(1.4)
    return np.stack([out, np.roll(out, 23)], axis=1)


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--out", default="start.wav")
    ap.add_argument("--seed", type=int, default=3)
    a = ap.parse_args()
    x = render(a.seed)
    with wave.open(a.out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    print(f"wrote {a.out}; the engine catches at {CATCH_AT} s")


if __name__ == "__main__":
    main()
