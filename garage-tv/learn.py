"""Learn as we go: make more of what viewers like.

Every published video gets a score from how it did in its first two weeks: views, likes (worth 10
views) and, once the channel's analytics permission is in place, subscribers gained (worth 50),
per day. The car engine then picks each part of the next video (room, scene, soundscape sound,
music style, car brand, title style, thumbnail layout) with odds that follow those scores:

- an option's score is shrunk toward the channel average until it has a few videos behind it,
  so one lucky video can't take over;
- every option always keeps a share of the odds, so new things keep getting tried and the
  channel doesn't get stuck on yesterday's winner.

Scores come from parked-fm/scoreboard.json (refreshed by the daily job) joined with
garage-tv/published.json. With no numbers yet every option has equal odds.

  python3 learn.py        # show what the channel has learned so far
"""
import datetime as dt
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SCOREBOARD = os.path.join(HERE, "..", "parked-fm", "scoreboard.json")
PUBLISHED = os.path.join(HERE, "published.json")
LIKE, SUBSCRIBER, SHORT_VIEW = 10, 50, 0.1  # what each counts for, in views
PRIOR = 3      # pretend every option already has this many average videos
FLOOR = 0.35   # every option keeps at least 35% of an equal share of the odds
WINDOW = 14    # score a video on its first two weeks


def load_board():
    try:
        with open(SCOREBOARD) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def scored(published, board=None, today=None):
    """[(published entry, score per day)] for every video YouTube has numbers for."""
    stats = {v["youtube"]: v for v in (board if board is not None else load_board()).get("videos", [])
             if v.get("views") is not None}
    today = today or dt.date.today()
    out = []
    for e in published:
        v = stats.get(e.get("youtube"))
        if not v:
            continue
        days = min(WINDOW, max(1, (today - dt.date.fromisoformat(e["date"])).days))
        points = (v["views"] + SHORT_VIEW * (v.get("short_views") or 0) + LIKE * (v.get("likes") or 0)
                  + SUBSCRIBER * (v.get("subscribers") or 0))
        out.append((e, points / days))
    return out


def odds(options, key, history):
    """{option: chance of being picked}. key(entry) says which option a past video used."""
    options = list(dict.fromkeys(options))
    if not options:
        return {}
    scores = [s for _, s in history]
    mean = sum(scores) / len(scores) if scores else 0.0
    w = {}
    for o in options:
        mine = [s for e, s in history if key(e) == o]
        w[o] = (sum(mine) + PRIOR * mean) / (len(mine) + PRIOR)
    total = sum(w.values())
    n = len(options)
    return {o: FLOOR / n + (1 - FLOOR) * (w[o] / total if total else 1 / n) for o in options}


def choose(rng, options, key, history):
    """Pick one option with the learned odds (rng: a random.Random)."""
    p = odds(options, key, history)
    items = list(p)
    return rng.choices(items, weights=[p[o] for o in items])[0]


def brand(car):
    return car.split()[0] if car else None


def report(published=None, board=None):
    """What the channel has learned so far, best first, as printable lines."""
    if published is None:
        with open(PUBLISHED) as f:
            published = json.load(f)
    history = scored(published, board)
    lines = [f"{len(history)} videos with numbers"]
    dims = [("scene", lambda e: e.get("scene")),
            ("soundscape", lambda e: e.get("recipe") if e.get("recipe") != "lofi" else None),
            ("music style", lambda e: e.get("music_style")),
            ("room", lambda e: e.get("room")),
            ("car brand", lambda e: brand(e.get("car"))),
            ("title style", lambda e: e.get("title_style")),
            ("thumbnail", lambda e: e.get("thumb_style")),
            ("picture maker", lambda e: e.get("maker"))]
    for name, key in dims:
        seen = [key(e) for e, _ in history if key(e)]
        if not seen:
            continue
        p = odds(seen, key, history)
        best = sorted(p.items(), key=lambda kv: -kv[1])
        lines.append(f"{name}: " + ", ".join(f"{o} {100 * v:.0f}%" for o, v in best))
    return lines


if __name__ == "__main__":
    print("\n".join(report()))
