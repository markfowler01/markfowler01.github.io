"""Clean synth voices for the electronic PARKED FM styles (future garage / chillstep, lo-fi house):
a warm detuned pad, a soft pluck for melodies and a round sub bass. Band-limited wavetables, so
nothing buzzes or aliases; no noise of any kind is generated.

Every voice returns float32 stereo at 44.1 kHz, shaped like the sample instruments' play().
"""
from functools import lru_cache

import numpy as np

SR = 44100
TABLE = 2048


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


@lru_cache(maxsize=None)
def _table(midi, kind):
    """One cycle of a saw, triangle or sine with harmonics kept under ~9 kHz."""
    ph = np.arange(TABLE) / TABLE * 2 * np.pi
    top = max(1, int(9000 // mtof(midi)))
    if kind == "saw":
        w = sum(np.sin(k * ph) / k for k in range(1, min(top, 60) + 1))
    elif kind == "tri":
        w = sum((-1) ** ((k - 1) // 2) * np.sin(k * ph) / k ** 2 for k in range(1, min(top, 31) + 1, 2))
    else:
        w = np.sin(ph)
    w = np.append(w, w[0])
    return w / np.abs(w).max()


def osc(midi, n, kind="sine", cents=0.0, phase=0.0):
    f = mtof(midi) * 2 ** (cents / 1200)
    idx = (phase + np.arange(n) * f / SR) % 1.0 * TABLE
    return np.interp(idx, np.arange(TABLE + 1), _table(midi, kind))


def envelope(n, attack, release, total):
    """Linear attack, hold until n, then an exponential-ish release out to `total` samples."""
    env = np.ones(total)
    a = min(int(attack * SR), n)
    if a:
        env[:a] = np.linspace(0, 1, a)
    tail = total - n
    if tail > 0:
        env[n:] = np.linspace(1, 0, tail) ** 2
    return env


def pad(midi, seconds, vel, rng):
    """Three slightly detuned saws spread across the stereo field, slow swell in and out."""
    n, rel = int(seconds * SR), 1.4
    total = n + int(rel * SR)
    ph = rng.random(3)
    left = osc(midi, total, "saw", -8, ph[0]) + 0.6 * osc(midi, total, "saw", 3, ph[1])
    right = osc(midi, total, "saw", 8, ph[2]) + 0.6 * osc(midi, total, "saw", -3, ph[1])
    env = envelope(n, 0.9, rel, total) * vel * 0.25
    return np.stack([left * env, right * env], axis=1).astype(np.float32)


def pluck(midi, seconds, vel, rng):
    """A soft triangle-and-sine pluck that fades like a felt mallet."""
    n = int((seconds + 0.6) * SR)
    t = np.arange(n) / SR
    x = 0.7 * osc(midi, n, "tri", 0, rng.random()) + 0.5 * osc(midi + 12, n, "sine")
    env = np.exp(-t / 0.45) * np.minimum(1, t / 0.004) * vel * 0.5
    x = x * env
    return np.stack([x, x], axis=1).astype(np.float32)


def sub(midi, seconds, vel, rng):
    """Round bass: a sine with a touch of its octave, quick soft attack, short release."""
    n, rel = int(seconds * SR), 0.08
    total = n + int(rel * SR)
    x = osc(midi, total, "sine") + 0.22 * osc(midi + 12, total, "sine") + 0.08 * osc(midi, total, "tri")
    x = x * envelope(n, 0.008, rel, total) * vel * 0.8
    return np.stack([x, x], axis=1).astype(np.float32)


def echo(x, delay, feedback=0.35, repeats=4):
    """Ping-pong echo: each repeat bounces to the other side and gets quieter."""
    d = int(delay * SR)
    out = np.concatenate([x, np.zeros((d * repeats, 2), x.dtype)])
    for i in range(1, repeats + 1):
        g = feedback ** i
        src = x[:, ::-1] if i % 2 else x
        out[i * d:i * d + len(x)] += src * g
    return out[:len(x)]
