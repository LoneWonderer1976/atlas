"""demo.py -- write a made-up docs/data.json so the page can be looked at before the first sync.

    python -m atlas.demo

Touches nothing in data/. The next `python -m atlas.stats` (or the hourly Action) overwrites it.
"""
import datetime as dt
import json
import math
import random

from . import stats, store
from .sync import HISTORY_START


def _track(lat, lon, n=150, r=0.006):
    return [[round(lat + r * math.sin(2 * math.pi * i / n), 5), round(lon + r * 1.6 * math.cos(2 * math.pi * i / n), 5)] for i in range(n + 1)]


def _stream(dist_m, dur_s, climb_m, rnd):
    """A timeline at 5 s intervals with pace that wanders +-15 %, so best efforts differ from averages."""
    n = max(2, int(dur_s // 5))
    t, d, alt, hr = [], [], [], []
    speed = dist_m / dur_s
    x = 0.0
    for i in range(n + 1):
        t.append(i * 5.0)
        d.append(round(x, 1))
        alt.append(round(40 + climb_m * (0.5 - 0.5 * math.cos(2 * math.pi * i / n)), 1))
        hr.append(int(130 + 30 * math.sin(math.pi * i / n) + rnd.uniform(-5, 5)))
        x += speed * 5 * (1 + 0.15 * math.sin(2 * math.pi * i / max(20, n / 3)) + rnd.uniform(-.05, .05))
    return {"t": t, "d": d, "alt": alt, "hr": hr}


def main() -> None:
    rnd = random.Random(11)
    plan = [("run", "running", 5.5, 45, 3.1), ("cycle", "road_biking", 28, 320, 7.4), ("run", "trail_running", 8, 140, 2.9),
            ("swim", "lap_swimming", 1.2, 0, 0.9), ("walk", "hiking", 9, 260, 1.4), ("run", "running", 3.2, 20, 3.4),
            ("cycle", "mountain_biking", 18, 410, 5.2), ("kayak", "kayaking", 6, 0, 1.7), ("run", "running", 10.5, 90, 3.0)]
    acts, streams, tracks = [], {}, {}
    day = max(HISTORY_START, dt.date(2026, 7, 3))
    i = 0
    while day <= dt.date.today():
        if rnd.random() < 0.55:
            sport, key, km, climb, base_speed = plan[i % len(plan)]
            fitness = 1 + 0.004 * (day - dt.date(2026, 7, 3)).days      # a little faster every week
            speed = base_speed * fitness * rnd.uniform(.93, 1.07)
            dist = km * 1000 * rnd.uniform(.8, 1.2)
            dur = dist / speed
            aid = 70000 + i
            acts.append({"id": aid, "name": key.replace("_", " ").title(), "sport": sport, "type_key": key,
                         "start_local": f"{day} {rnd.randint(6, 19):02d}:{rnd.randint(0, 59):02d}:00",
                         "distance_m": round(dist, 1), "ascent_m": round(climb * rnd.uniform(.7, 1.3), 1), "duration_s": round(dur),
                         "avg_hr": rnd.randint(135, 165) if sport != "swim" else None, "max_hr": rnd.randint(170, 190),
                         "avg_speed_mps": round(speed, 2), "avg_cadence": 168 if sport == "run" else None, "calories": round(dist / 15)})
            streams[aid] = _stream(dist, dur, climb, rnd)
            if sport not in ("swim",):
                tracks[aid] = _track(50.92 + rnd.uniform(-.03, .03), -1.29 + rnd.uniform(-.03, .03))
            i += 1
        day += dt.timedelta(days=1)
    real = store.has_track
    store.has_track = lambda x: x in tracks
    try:
        data = stats.build(acts, {"exclude": {str(70000 + 4): "watch left running"}, "sport": {}}, streams=lambda x: streams.get(x))
    finally:
        store.has_track = real
    store.DOCS.mkdir(exist_ok=True)
    (store.DOCS / "tracks").mkdir(exist_ok=True)
    (store.DOCS / "data.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    for aid, pts in tracks.items():
        (store.DOCS / "tracks" / f"{aid}.json").write_text(json.dumps({"id": aid, "points": pts}))
    print(f"DEMO data.json written ({len(acts)} made-up activities, {len(data['records'])} records) -- `python -m atlas.stats` puts the real one back")


if __name__ == "__main__":
    main()
