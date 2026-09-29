#!/usr/bin/env python3
"""Generate a calm garage soundscape as a WAV file.

Layers:
  - brown noise  : HVAC / shop fan rumble (the "white noise" bed)
  - pink noise   : gentle air hiss, slowly breathing in volume
  - hum          : 60 Hz mains hum with soft harmonics (fluorescents, chargers)
  - compressor   : an air compressor that kicks on every few minutes, runs,
                   and fades out (optional, off by default for max chill)
  - drips        : rare soft "tink" of a tool set down or a drip (optional)

Usage:
  python3 make_ambience.py --minutes 60 --out ambience.wav
  python3 make_ambience.py --minutes 5 --compressor --out ambience.wav
"""
import argparse
import math
import wave

import numpy as np

SR = 44100


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=5)
    ap.add_argument("--out", default="ambience.wav")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--compressor", action="store_true", help="add occasional air-compressor cycles")
    ap.add_argument("--hum", type=float, default=0.06, help="mains hum level 0-1")
    ap.add_argument("--rumble", type=float, default=0.55, help="brown-noise fan level 0-1")
    ap.add_argument("--hiss", type=float, default=0.18, help="pink-noise air level 0-1")
    ap.add_argument("--seamless", action="store_true",
                    help="no fade in/out; crossfade the tail into the head so the file loops cleanly")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    n = int(args.minutes * 60 * SR)
    xf = int(6 * SR) if args.seamless else 0  # crossfade length
    n += xf

    print(f"rendering {args.minutes} min ({n} samples)...")
    rumble = lowpass_fast(brown_noise(n, rng), 220) * slow_lfo(n, 47, rng, 0.35)
    hiss = lowpass_fast(pink_noise(n, rng), 4000) * slow_lfo(n, 23, rng, 0.6)
    mains = hum(n) * slow_lfo(n, 90, rng, 0.2)

    mix = args.rumble * rumble / (np.abs(rumble).max() + 1e-9)
    mix += args.hiss * hiss / (np.abs(hiss).max() + 1e-9)
    mix += args.hum * mains
    if args.compressor:
        mix += 0.28 * compressor_events(n, rng)

    # soft-clip / normalise to -6 dBFS so it's polite on a TV
    mix = np.tanh(mix * 1.4)
    mix *= 0.5 / (np.abs(mix).max() + 1e-9)
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
