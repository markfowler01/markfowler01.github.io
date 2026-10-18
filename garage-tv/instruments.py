#!/usr/bin/env python3
"""Play real recorded instruments (SFZ sample libraries) from Python, for the lo-fi creator.

An SFZ file maps recordings to keys and loudness: each <region> names a sample and the notes
(lokey..hikey, pitch_keycenter) and velocities (lovel..hivel) it covers, with optional round
robins (lorand..hirand) so repeated notes don't sound identical. This module reads that map,
picks the right recording for a note, pitches it to the exact note and shapes its release.

Libraries are cloned from github.com/sfzinstruments with only the samples actually played
fetched (git partial clone), into garage-tv/out/instruments (ignored by git).

  piano = SfzInstrument.open("jlearman.jRhodes3d", "<path to .sfz>")
  note = piano.play(60, 0.7, 1.5, rng)          # (samples, 2) float32 array at 44.1 kHz
"""
import glob
import os
import re
import subprocess

import numpy as np

import imageio_ffmpeg

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "out", "instruments")
NOTE = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}


def note_number(v):
    """SFZ key: a MIDI number or a note name like c4 / f#3 / eb2 (c4 = 60)."""
    v = str(v).strip().lower()
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    m = re.fullmatch(r"([a-g])([#b]?)(-?\d+)", v)
    if not m:
        raise ValueError(f"bad key {v!r}")
    n = NOTE[m.group(1)] + {"#": 1, "b": -1, "": 0}[m.group(2)]
    return n + 12 * (int(m.group(3)) + 1)


def clone(repo):
    """Partial clone (file list only); samples are fetched the first time they are played."""
    path = os.path.join(STORE, repo)
    if not os.path.isdir(os.path.join(path, ".git")):
        os.makedirs(STORE, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", "--depth", "1",
                        f"https://github.com/sfzinstruments/{repo}", path], check=True)
        subprocess.run(["git", "-C", path, "checkout", "-q", "HEAD", "--", "."], check=False,
                       env=dict(os.environ, GIT_NO_LAZY_FETCH="1"), stderr=subprocess.DEVNULL)
    return path


def ensure(repo_path, rel):
    """Make sure one file of a partial clone is on disk (fetch its blob if needed)."""
    full = os.path.join(repo_path, rel)
    if not os.path.exists(full):
        subprocess.run(["git", "-C", repo_path, "checkout", "-q", "HEAD", "--", rel], check=True)
    return full


def ensure_many(repo_path, rels):
    missing = [r for r in rels if not os.path.exists(os.path.join(repo_path, r))]
    for i in range(0, len(missing), 200):
        subprocess.run(["git", "-C", repo_path, "checkout", "-q", "HEAD", "--", *missing[i:i + 200]], check=True)


_cache = {}


def load(path):
    """Decode any sample file to float32 stereo at 44.1 kHz (cached)."""
    if path not in _cache:
        raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-i", path,
                              "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
        _cache[path] = np.frombuffer(raw, np.float32).reshape(-1, 2)
    return _cache[path]


def parse_sfz(text_of, start):
    """Return a list of region opcode dicts with <control>/<global>/<master>/<group> inherited.
    text_of(relpath) gives a file's text; #include and #define are followed."""
    defines = {}
    regions = []
    levels = {"control": {}, "global": {}, "master": {}, "group": {}}
    current = None  # the header currently being filled
    order = ["control", "global", "master", "group"]

    def lines_of(rel):
        base = os.path.dirname(rel)
        for raw in text_of(rel).splitlines():
            line = raw.split("//")[0].strip()
            if not line:
                continue
            m = re.match(r'#include\s+"([^"]+)"', line)
            if m:
                yield from lines_of(os.path.normpath(os.path.join(base, m.group(1).replace("\\", "/"))))
                continue
            m = re.match(r"#define\s+(\$\w+)\s+(.*)", line)
            if m:
                defines[m.group(1)] = m.group(2).strip()
                continue
            for k, v in defines.items():
                line = line.replace(k, v)
            yield line

    def flush():
        if current is not None and current[0] == "region":
            merged = {}
            for name in order:
                merged.update(levels[name])
            merged.update(current[1])
            regions.append(merged)

    for line in lines_of(start):
        # a line can hold several headers and opcodes: split on headers first
        for part in re.split(r"(<\w+>)", line):
            part = part.strip()
            if not part:
                continue
            h = re.fullmatch(r"<(\w+)>", part)
            if h:
                flush()
                name = h.group(1)
                if name in levels:
                    # a new header resets itself and everything below it
                    for lower in order[order.index(name):]:
                        levels[lower] = {}
                    current = (name, levels[name])
                else:
                    current = (name, {})
                continue
            if current is None:
                continue
            # opcodes: key=value, where a value (e.g. a sample path) may contain spaces
            for k, v in re.findall(r"(\w+)=(.*?)(?=\s+\w+=|$)", part):
                current[1][k] = v.strip()
    flush()
    return regions


class SfzInstrument:
    def __init__(self, repo, sfz_rel, release=None, gain=1.0):
        self.repo = repo
        self.path = clone(repo)
        self.release = release
        self.gain = gain
        base = os.path.dirname(sfz_rel)

        def text_of(rel):
            return open(ensure(self.path, rel), encoding="utf-8", errors="replace").read()

        self.regions = []
        default_path = ""
        for r in parse_sfz(text_of, sfz_rel):
            if r.get("trigger", "attack") != "attack" or "sw_last" in r or "locc64" in r:
                continue  # release noises, keyswitches and pedal layers aren't used
            default_path = r.get("default_path", default_path).replace("\\", "/")
            if "sample" not in r:
                continue
            key = r.get("key")
            lo = note_number(r.get("lokey", key if key is not None else 0))
            hi = note_number(r.get("hikey", key if key is not None else 127))
            center = note_number(r.get("pitch_keycenter", key if key is not None else lo))
            self.regions.append(dict(
                sample=os.path.normpath(os.path.join(base, default_path, r["sample"].replace("\\", "/"))),
                lo=lo, hi=hi, center=center,
                lovel=int(float(r.get("lovel", 1))), hivel=int(float(r.get("hivel", 127))),
                lorand=float(r.get("lorand", 0)), hirand=float(r.get("hirand", 1)),
                tune=float(r.get("tune", 0)) + 100 * float(r.get("transpose", 0)),
                volume=float(r.get("volume", 0)) + float(r.get("amplitude", 100)) / 100 * 0,
                offset=int(float(r.get("offset", 0))),
                release=float(r.get("ampeg_release", 0.3)),
            ))
        if not self.regions:
            raise SystemExit(f"{repo}/{sfz_rel}: no playable regions found")

    def keys(self):
        return min(r["lo"] for r in self.regions), max(r["hi"] for r in self.regions)

    def pick(self, note, vel, rng):
        v = int(np.clip(round(vel * 127), 1, 127))
        hits = [r for r in self.regions if r["lo"] <= note <= r["hi"] and r["lovel"] <= v <= r["hivel"]]
        if not hits:  # out of range: nearest key, then nearest velocity
            near = min(self.regions, key=lambda r: (min(abs(note - r["lo"]), abs(note - r["hi"])),
                                                    min(abs(v - r["lovel"]), abs(v - r["hivel"]))))
            hits = [r for r in self.regions if (r["lo"], r["hi"], r["lovel"], r["hivel"]) ==
                    (near["lo"], near["hi"], near["lovel"], near["hivel"])]
        x = rng.random()
        rr = [r for r in hits if r["lorand"] <= x < r["hirand"]] or hits
        return rr[int(rng.integers(len(rr)))]

    def play(self, note, vel, dur, rng, cents=0.0):
        """One note: `dur` seconds held, then the region's release. Returns (n, 2) float32."""
        r = self.pick(note, vel, rng)
        s = load(ensure(self.path, r["sample"]))[r["offset"]:]
        ratio = 2 ** ((note - r["center"]) / 12 + (r["tune"] + cents) / 1200)
        rel = self.release if self.release is not None else r["release"]
        n_out = int((dur + rel) * SR)
        need = min(len(s), int(n_out * ratio) + 2)
        if abs(ratio - 1) > 1e-4:
            pos = np.arange(0, need - 1, ratio)[:n_out]
            out = np.stack([np.interp(pos, np.arange(need), s[:need, c]) for c in (0, 1)], axis=1)
        else:
            out = s[:n_out].copy()
        t = np.arange(len(out)) / SR
        out *= np.where(t > dur, np.exp(-(t - dur) / max(rel / 4, 0.01)), 1.0)[:, None]
        g = self.gain * (0.25 + 0.75 * vel) * 10 ** (r["volume"] / 20)
        return (out * g).astype(np.float32)


class DrumFolder:
    """One drum from a folder of one-shot samples named like ..._vl3_rr2.flac (velocity layer,
    round robin), e.g. virtuosity_drums Samples/lofi/kick."""

    def __init__(self, repo, folder, pattern="*", gain=1.0):
        self.path = clone(repo)
        listing = subprocess.run(["git", "-C", self.path, "ls-tree", "-r", "--name-only", "HEAD", folder],
                                 capture_output=True, text=True, check=True).stdout.split()
        names = [p for p in listing if glob.fnmatch.fnmatch(os.path.basename(p), pattern)
                 and p.lower().endswith((".wav", ".flac", ".ogg"))]
        if not names:
            raise SystemExit(f"{repo}/{folder}/{pattern}: no samples")
        ensure_many(self.path, names)
        self.layers = {}
        for p in names:
            m = re.search(r"vl(\d+)", os.path.basename(p))
            self.layers.setdefault(int(m.group(1)) if m else 1, []).append(p)
        self.gain = gain

    def play(self, vel, rng):
        levels = sorted(self.layers)
        layer = levels[min(len(levels) - 1, int(vel * len(levels)))]
        p = self.layers[layer][int(rng.integers(len(self.layers[layer])))]
        return (load(os.path.join(self.path, p)) * self.gain * (0.35 + 0.65 * vel)).astype(np.float32)


def detect_pitch(x):
    """Rough fundamental of a mono note (Hz): autocorrelation peak over 25 Hz to 2 kHz."""
    x = x[int(0.05 * SR):int(0.55 * SR)]
    x = x - x.mean()
    n = 1 << (2 * len(x) - 1).bit_length()
    X = np.fft.rfft(x, n)
    ac = np.fft.irfft(X * np.conj(X), n)[:len(x)]
    lo, hi = int(SR / 2000), int(SR / 25)
    lag = lo + int(np.argmax(ac[lo:hi]))
    return SR / lag


class NoteFolder:
    """A pitched instrument from sample files whose names say the note, e.g.
    Piano_UC_MicA_A4_vl2.flac or sneakybass_eb2_finger_rr3.wav. `regex` must have a group
    `note` and may have `vl` (loudness layer, ordered by `vl_order` or numerically) and `rr`.
    The octave numbering of the file names is checked against the real pitch of a sample."""

    def __init__(self, repo, folder, regex, vl_order=None, gain=1.0, release=0.25, max_len=6.0):
        self.path = clone(repo)
        listing = subprocess.run(["git", "-C", self.path, "ls-tree", "-r", "--name-only", "HEAD", folder],
                                 capture_output=True, text=True, check=True).stdout.split()
        rx = re.compile(regex, re.I)
        self.samples = []  # (midi note, layer index, path)
        layers = set()
        for p in listing:
            m = rx.search(os.path.basename(p))
            if not m:
                continue
            vl = (m.groupdict().get("vl") or "1").lower()
            layers.add(vl)
            self.samples.append([note_number(m.group("note")), vl, p])
        if not self.samples:
            raise SystemExit(f"{repo}/{folder}: no samples matched {regex}")
        order = vl_order or sorted(layers, key=lambda v: float(v) if v.replace(".", "").isdigit() else v)
        rank = {v: i for i, v in enumerate([v.lower() for v in order])}
        for s in self.samples:
            s[1] = rank.get(s[1], 0)
        self.n_layers = max(s[1] for s in self.samples) + 1
        ensure_many(self.path, [s[2] for s in self.samples])
        # check the file names' octave numbering against a real pitch near the middle
        mid = sorted(self.samples, key=lambda s: abs(s[0] - 57))[0]
        f0 = detect_pitch(load(os.path.join(self.path, mid[2])).mean(axis=1))
        expected = 440 * 2 ** ((mid[0] - 69) / 12)
        self.shift = 12 * round(np.log2(f0 / expected))
        for s in self.samples:
            s[0] += self.shift
        self.gain, self.release, self.max_len = gain, release, max_len
        self.notes = sorted({s[0] for s in self.samples})
        print(f"{repo}/{folder}: {len(self.samples)} samples, notes {self.notes[0]}-{self.notes[-1]}, "
              f"{self.n_layers} layers, octave fix {self.shift:+d} (heard {f0:.1f} Hz for {os.path.basename(mid[2])})")

    def play(self, note, vel, dur, rng, cents=0.0):
        layer = min(self.n_layers - 1, int(vel * self.n_layers))
        near = min(self.notes, key=lambda n: (abs(n - note), n < note))
        cands = [s for s in self.samples if s[0] == near and s[1] == layer] or [s for s in self.samples if s[0] == near]
        root, _, p = cands[int(rng.integers(len(cands)))]
        s = load(os.path.join(self.path, p))
        ratio = 2 ** ((note - root) / 12 + cents / 1200)
        n_out = int(min(dur + self.release, self.max_len) * SR)
        need = min(len(s), int(n_out * ratio) + 2)
        if abs(ratio - 1) > 1e-4:
            pos = np.arange(0, need - 1, ratio)[:n_out]
            out = np.stack([np.interp(pos, np.arange(need), s[:need, c]) for c in (0, 1)], axis=1)
        else:
            out = s[:n_out].copy()
        t = np.arange(len(out)) / SR
        out *= np.where(t > dur, np.exp(-(t - dur) / max(self.release / 4, 0.01)), 1.0)[:, None]
        fade = min(len(out), int(0.01 * SR))
        out[len(out) - fade:] *= np.linspace(1, 0, fade)[:, None]
        return (out * self.gain * (0.3 + 0.7 * vel)).astype(np.float32)
