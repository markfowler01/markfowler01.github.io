#!/usr/bin/env python3
"""Generate a calm garage soundscape as a WAV file.

Layers:
  - brown noise  : HVAC / shop fan rumble (the "white noise" bed)
  - pink noise   : gentle air hiss, slowly breathing in volume
  - hum          : 60 Hz mains hum with soft harmonics (fluorescents, chargers)
  - compressor   : an air compressor that kicks on every few minutes, runs,
                   and fades out (optional, off by default for max chill)
  - recipe layer : rain on the roof, unit heater, or wind outside (--recipe)

Usage:
  python3 make_ambience.py --minutes 60 --out ambience.wav
  python3 make_ambience.py --minutes 2 --recipe rain --seamless --out rain.wav
"""
import argparse
import math
import wave

import numpy as np

SR = 44100
TARGET_RMS = 0.06  # about -24 dBFS average: quiet and even, like the first published video


def brown_noise(n, rng):
    white = rng.standard_normal(n)
    b = np.cumsum(white)
    # leaky integrator so it doesn't wander off
    b -= np.convolve(b, np.ones(2000) / 2000, mode="same")
    return b / (np.abs(b).max() + 1e-9)


def pink_noise(n, rng):
    # Voss-McCartney-ish via summing octave-band white noise
    rows = 12
    out = np.zeros(n)
    for r in range(rows):
        step = 2 ** r
        vals = rng.standard_normal(n // step + 1)
        out += np.repeat(vals, step)[:n]
    return out / (np.abs(out).max() + 1e-9)


def lowpass(x, cutoff_hz):
    # simple one-pole IIR lowpass
    rc = 1.0 / (2 * math.pi * cutoff_hz)
    dt = 1.0 / SR
    a = dt / (rc + dt)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a * (x[i] - acc)
        y[i] = acc
    return y


def lowpass_fast(x, cutoff_hz):
    # FFT-based lowpass for long signals (much faster than the loop)
    X = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    gain = 1.0 / np.sqrt(1 + (freqs / cutoff_hz) ** 4)  # gentle 2-pole
    return np.fft.irfft(X * gain, n=len(x))


def slow_lfo(n, period_s, rng, depth=0.5):
    t = np.arange(n) / SR
    phase = rng.uniform(0, 2 * math.pi)
    return 1 - depth * 0.5 * (1 + np.sin(2 * math.pi * t / period_s + phase))


def hum(n, base=60.0):
    t = np.arange(n) / SR
    h = (np.sin(2 * math.pi * base * t)
         + 0.35 * np.sin(2 * math.pi * base * 2 * t)
         + 0.15 * np.sin(2 * math.pi * base * 3 * t)
         + 0.08 * np.sin(2 * math.pi * base * 5 * t))
    return h / np.abs(h).max()


def fade_edges(x, seconds=3.0):
    k = int(seconds * SR)
    ramp = np.linspace(0, 1, k)
    x[:k] *= ramp
    x[-k:] *= ramp[::-1]
    return x


def compressor_events(n, rng, every_s=(180, 420), run_s=(25, 45)):
    """Air compressor kicks on occasionally: a filtered noise burst + motor tone."""
    out = np.zeros(n)
    t0 = rng.uniform(60, every_s[1])
    while t0 * SR < n:
        run = rng.uniform(*run_s)
        s = int(t0 * SR)
        e = min(n, int((t0 + run) * SR))
        m = e - s
        if m <= SR:
            break
        motor_t = np.arange(m) / SR
        motor = 0.6 * np.sin(2 * math.pi * 48 * motor_t) + 0.3 * np.sin(2 * math.pi * 96 * motor_t)
        noise = lowpass_fast(rng.standard_normal(m), 900)
        noise /= np.abs(noise).max() + 1e-9
        env = np.ones(m)
        k = int(1.5 * SR)
        env[:k] = np.linspace(0, 1, k)
        env[-k:] = np.linspace(1, 0, k)
        out[s:e] += env * (0.5 * motor + 0.5 * noise)
        t0 += run + rng.uniform(*every_s)
    return out


def bandpass_fast(x, lo_hz, hi_hz):
    """FFT band-pass: gentle 2-pole high-pass at lo_hz, 2-pole low-pass at hi_hz."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    hp = (f / lo_hz) ** 2 / np.sqrt(1 + (f / lo_hz) ** 4)
    lp = 1.0 / np.sqrt(1 + (f / hi_hz) ** 4)
    return np.fft.irfft(X * hp * lp, n=len(x))


def norm(x):
    return x / (np.abs(x).max() + 1e-9)


def rain_road_layer(n, rng):
    """Outdoor rain on a wet road and forest: mostly a soft, wide wash, very few individual drops."""
    wash = bandpass_fast(rng.standard_normal(n), 180, 2600) * slow_lfo(n, 37, rng, 0.2)
    body = lowpass_fast(rng.standard_normal(n), 500)  # the low "roar" of rain over a wide area
    return 0.75 * norm(wash) + 0.35 * norm(body) + 0.25 * norm(rain_layer(n, rng, drops_only=True))


def rain_layer(n, rng, drops_only=False):
    """Steady rain on a metal shop roof: a soft wash plus thousands of tiny, dull drop ticks."""
    wash = bandpass_fast(rng.standard_normal(n), 250, 2200) * slow_lfo(n, 31, rng, 0.25)
    # drops: sparse impulses (about 60/s) with random size, smeared by a short decaying burst
    impulses = np.zeros(n)
    k = int(n / SR * 60)
    pos = rng.integers(0, n, k)
    impulses[pos] = rng.pareto(3.0, k) * rng.choice([-1, 1], k)
    klen = int(0.012 * SR)
    kern = rng.standard_normal(klen) * np.exp(-np.arange(klen) / (0.0025 * SR))
    drops = np.fft.irfft(np.fft.rfft(impulses) * np.fft.rfft(kern, n=n), n=n)
    drops = lowpass_fast(drops, 2400)  # dull the ticks so nothing is sharp enough to wake anyone
    if drops_only:
        return drops
    return 0.7 * norm(wash) + 0.45 * norm(drops)


def heater_layer(n, rng):
    """Shop unit heater: blower whoosh plus a low motor tone that wavers slightly."""
    t = np.arange(n) / SR
    wobble = 1 + 0.004 * np.sin(2 * math.pi * t / 13 + rng.uniform(0, 6.28))
    phase = 2 * math.pi * 29.5 * np.cumsum(wobble) / SR
    motor = np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.2 * np.sin(4 * phase)
    blower = bandpass_fast(rng.standard_normal(n), 80, 1100)
    return 0.8 * norm(blower) + 0.25 * norm(motor)


def wind_layer(n, rng):
    """Wind outside the bay door: slow gusts that swell and settle, darker when calm."""
    base = rng.standard_normal(n)
    dark = norm(lowpass_fast(base, 350))
    bright = norm(bandpass_fast(base, 250, 1400))
    t = np.arange(n) / SR
    g = (0.5 + 0.5 * np.sin(2 * math.pi * t / 19 + rng.uniform(0, 6.28))) * \
        (0.6 + 0.4 * np.sin(2 * math.pi * t / 47 + rng.uniform(0, 6.28)))
    return 0.8 * dark * (0.5 + 0.5 * g) + 0.5 * bright * g


# Each recipe sets the base levels and an extra layer. Flags still override the levels.
RECIPES = {
    "fan":    dict(rumble=0.55, hiss=0.18, hum=0.06, extra=None, extra_level=0.0),
    "rain":   dict(rumble=0.30, hiss=0.05, hum=0.03, extra=rain_layer, extra_level=0.55),
    "rain_road": dict(rumble=0.22, hiss=0.04, hum=0.0, extra=rain_road_layer, extra_level=0.65),
    "heater": dict(rumble=0.45, hiss=0.08, hum=0.03, extra=heater_layer, extra_level=0.45),
    "wind":   dict(rumble=0.35, hiss=0.06, hum=0.03, extra=wind_layer, extra_level=0.50),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=5)
    ap.add_argument("--out", default="ambience.wav")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--recipe", choices=RECIPES, default="fan",
                    help="fan (shop fan), rain (rain on the roof), heater (unit heater), wind (wind outside)")
    ap.add_argument("--compressor", action="store_true", help="add occasional air-compressor cycles")
    ap.add_argument("--hum", type=float, default=None, help="mains hum level 0-1")
    ap.add_argument("--rumble", type=float, default=None, help="brown-noise fan level 0-1")
    ap.add_argument("--hiss", type=float, default=None, help="pink-noise air level 0-1")
    ap.add_argument("--seamless", action="store_true",
                    help="no fade in/out; crossfade the tail into the head so the file loops cleanly")
    args = ap.parse_args()
    r = RECIPES[args.recipe]
    lv = {k: (getattr(args, k) if getattr(args, k) is not None else r[k]) for k in ("rumble", "hiss", "hum")}

    rng = np.random.default_rng(args.seed)
    n = int(args.minutes * 60 * SR)
    xf = int(6 * SR) if args.seamless else 0  # crossfade length
    n += xf

    print(f"rendering {args.minutes} min of '{args.recipe}' ({n} samples)...")
    rumble = lowpass_fast(brown_noise(n, rng), 220) * slow_lfo(n, 47, rng, 0.35)
    hiss = lowpass_fast(pink_noise(n, rng), 4000) * slow_lfo(n, 23, rng, 0.6)
    mains = hum(n) * slow_lfo(n, 90, rng, 0.2)

    mix = lv["rumble"] * norm(rumble)
    mix += lv["hiss"] * norm(hiss)
    mix += lv["hum"] * mains
    if r["extra"] is not None:
        mix += r["extra_level"] * norm(r["extra"](n, rng))
    if args.compressor:
        mix += 0.28 * compressor_events(n, rng)

    # level by average loudness (not peak) so every recipe plays at the same volume,
    # then soft-limit any peaks above 0.8 so nothing jumps out
    mix *= TARGET_RMS / (np.sqrt((mix ** 2).mean()) + 1e-12)
    mix = 0.8 * np.tanh(mix / 0.8)
    if args.seamless:
        # equal-power crossfade: the extra tail blends into the head, then is dropped
        ramp = np.linspace(0, 1, xf)
        head, tail = mix[:xf], mix[-xf:]
        mix = mix[:-xf].copy()
        mix[:xf] = head * np.sqrt(ramp) + tail * np.sqrt(1 - ramp)
    else:
        mix = fade_edges(mix, 4.0)

    # slight stereo width: delay right channel a hair and decorrelate hiss
    right = np.roll(mix, 37)
    stereo = np.stack([mix, right], axis=1)
    pcm = (stereo * 32767).astype(np.int16)

    with wave.open(args.out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("wrote", args.out)


if __name__ == "__main__":
    main()
