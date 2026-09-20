"""records.py -- best efforts from an activity's timeline, and the records board across them.

A best effort is the FASTEST STRETCH of a target distance anywhere inside an activity -- the
quickest 5 km inside a 12 km run, not the run's average. `best_efforts(stream, targets)` finds
each with a two-pointer sweep over the device's cumulative distance (O(n)), interpolating the
finish time to the exact distance so a 5,003 m window does not read as a 5 km.

`board(rows)` then builds the records: the fastest of each target per sport across every
activity that has one, plus the summary-level records (longest, most climb, longest time,
fastest average over a floor distance, biggest week and month). Everything is recomputed from
the streams on every run; nothing here is stored.
"""
import bisect
import datetime as dt

MI = 1609.344

# targets per sport, in metres, with a short label -- the ladder a runner or rider actually quotes
TARGETS = {
    "run":   [(400, "400 m"), (1000, "1 km"), (MI, "1 mile"), (5000, "5 km"), (10000, "10 km"),
              (21097.5, "Half marathon"), (42195, "Marathon")],
    "cycle": [(5000, "5 km"), (10000, "10 km"), (10 * MI, "10 miles"), (20000, "20 km"), (40000, "40 km"),
              (50 * MI, "50 miles"), (100000, "100 km")],
    "walk":  [(MI, "1 mile"), (5000, "5 km"), (10000, "10 km"), (20000, "20 km")],
    "swim":  [(100, "100 m"), (200, "200 m"), (400, "400 m"), (1000, "1 km"), (MI, "1 mile")],
    "kayak": [(1000, "1 km"), (5000, "5 km"), (10000, "10 km")],
}

# the floor a "fastest average" record needs, so a 300 m sprint is not the fastest run
AVG_FLOOR_M = {"run": 3000, "cycle": 10000, "walk": 3000, "swim": 400, "kayak": 2000}


def fastest(t: list, d: list, target: float) -> tuple[float, int, int] | None:
    """(seconds, start index, end index) of the fastest window covering `target` metres, or None
    if the activity is shorter than the target. Times are interpolated at the exact distance."""
    n = len(d)
    if n < 2 or d[-1] - d[0] < target:
        return None
    best = None
    j = 0
    for i in range(n):
        goal = d[i] + target
        if goal > d[-1]:
            break
        j = max(j, i + 1)
        j = bisect.bisect_left(d, goal, j)     # first index with d[j] >= goal
        if j >= n:
            break
        # interpolate the crossing time between j-1 and j
        if d[j] == goal or j == 0 or d[j] == d[j - 1]:
            t_end = t[j]
        else:
            frac = (goal - d[j - 1]) / (d[j] - d[j - 1])
            t_end = t[j - 1] + frac * (t[j] - t[j - 1])
        secs = t_end - t[i]
        if secs > 0 and (best is None or secs < best[0]):
            best = (round(secs, 1), i, j)
    return best


def best_efforts(stream: dict | None, sport: str) -> dict[str, float]:
    """{label: seconds} for every target the activity covers."""
    if not stream or not stream.get("t") or len(stream["t"]) < 2:
        return {}
    out = {}
    for metres, label in TARGETS.get(sport, []):
        r = fastest(stream["t"], stream["d"], metres)
        if r:
            out[label] = r[0]
    return out


def fmt_time(secs: float) -> str:
    s = int(round(secs))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def pace_str(secs_per_km: float, sport: str) -> str:
    """min/mile for feet, km/h for wheels and paddles, min/100 m for water."""
    if sport in ("run", "walk"):
        per_mi = secs_per_km * MI / 1000
        return f"{int(per_mi // 60)}:{int(per_mi % 60):02d} /mi"
    if sport == "swim":
        per_100 = secs_per_km / 10
        return f"{int(per_100 // 60)}:{int(per_100 % 60):02d} /100m"
    return f"{3600 / secs_per_km:.1f} km/h" if secs_per_km else ""


def board(rows: list[dict]) -> list[dict]:
    """The records: one entry per (sport, target) and per summary record, each naming the activity
    and date it stands on. `rows` are stats.py's scored rows with `efforts` already attached."""
    out = []
    by_sport: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("excluded"):
            continue
        by_sport.setdefault(r["sport"], []).append(r)
    for sport, acts in by_sport.items():
        for metres, label in TARGETS.get(sport, []):
            cands = [(a["efforts"][label], a) for a in acts if label in a.get("efforts", {})]
            if not cands:
                continue
            secs, a = min(cands, key=lambda x: x[0])
            out.append({"sport": sport, "kind": "effort", "label": label, "metres": metres, "seconds": secs,
                        "display": fmt_time(secs), "sub": pace_str(secs / (metres / 1000), sport),
                        "activity_id": a["id"], "date": a["date"], "name": a["name"]})
        longest = max(acts, key=lambda a: a.get("distance_m") or 0)
        if longest.get("distance_m"):
            out.append({"sport": sport, "kind": "longest", "label": "Longest", "display": _dist(longest["distance_m"], sport),
                        "sub": fmt_time(longest.get("duration_s") or 0), "activity_id": longest["id"],
                        "date": longest["date"], "name": longest["name"], "value": longest["distance_m"]})
        climb = max(acts, key=lambda a: a.get("ascent_m") or 0)
        if (climb.get("ascent_m") or 0) > 0 and sport != "swim":
            out.append({"sport": sport, "kind": "climb", "label": "Most climb", "display": f"{climb['ascent_m']:.0f} m",
                        "sub": _dist(climb.get("distance_m") or 0, sport), "activity_id": climb["id"],
                        "date": climb["date"], "name": climb["name"], "value": climb["ascent_m"]})
        longest_t = max(acts, key=lambda a: a.get("duration_s") or 0)
        if longest_t.get("duration_s"):
            out.append({"sport": sport, "kind": "duration", "label": "Longest time", "display": fmt_time(longest_t["duration_s"]),
                        "sub": _dist(longest_t.get("distance_m") or 0, sport), "activity_id": longest_t["id"],
                        "date": longest_t["date"], "name": longest_t["name"], "value": longest_t["duration_s"]})
        floor = AVG_FLOOR_M.get(sport, 0)
        eligible = [a for a in acts if (a.get("distance_m") or 0) >= floor and a.get("avg_speed_mps")]
        if eligible:
            fast = max(eligible, key=lambda a: a["avg_speed_mps"])
            spk = 1000 / fast["avg_speed_mps"]
            out.append({"sport": sport, "kind": "average", "label": f"Fastest average (≥ {_dist(floor, sport)})",
                        "display": pace_str(spk, sport), "sub": _dist(fast["distance_m"], sport), "activity_id": fast["id"],
                        "date": fast["date"], "name": fast["name"], "value": fast["avg_speed_mps"]})
    # biggest week and month, all sports, by distance
    weeks: dict[str, float] = {}
    months: dict[str, float] = {}
    for r in rows:
        if r.get("excluded"):
            continue
        weeks[r["week"]] = weeks.get(r["week"], 0) + (r.get("distance_m") or 0)
        months[r["date"][:7]] = months.get(r["date"][:7], 0) + (r.get("distance_m") or 0)
    if weeks:
        w = max(weeks, key=weeks.get)
        out.append({"sport": "all", "kind": "week", "label": "Biggest week", "display": f"{weeks[w] / 1000:.1f} km",
                    "sub": f"week of {w}", "date": w, "value": weeks[w]})
    if months:
        m = max(months, key=months.get)
        out.append({"sport": "all", "kind": "month", "label": "Biggest month", "display": f"{months[m] / 1000:.1f} km",
                    "sub": dt.date.fromisoformat(m + "-01").strftime("%B %Y"), "date": m + "-01", "value": months[m]})
    return out


def _dist(m: float, sport: str) -> str:
    return f"{m:.0f} m" if sport == "swim" else f"{m / MI:.1f} mi"


def selftest() -> None:
    # a 3 km run at a steady 5:00/km except a fast middle km at 4:00
    t, d = [0.0], [0.0]
    for i in range(1, 301):
        d.append(i * 10.0)
        pace = 0.24 if 1000 <= i * 10 <= 2000 else 0.30      # seconds per metre
        t.append(t[-1] + pace * 10)
    best = fastest(t, d, 1000)
    assert best and abs(best[0] - 240.0) < 0.6, best
    assert fastest(t, d, 5000) is None
    assert abs(fastest(t, d, 400)[0] - 96.0) < 0.6
    assert fastest([0, 10], [0, 5], 100) is None and fastest([0], [0], 1) is None
    # interpolation: 2 points, 100 m in 40 s; the fastest 50 m is 20 s
    assert fastest([0.0, 40.0], [0.0, 100.0], 50)[0] == 20.0
    eff = best_efforts({"t": t, "d": d}, "run")
    assert set(eff) == {"400 m", "1 km", "1 mile"} and abs(eff["1 km"] - 240) < 1
    assert best_efforts(None, "run") == {} and best_efforts({"t": [0], "d": [0]}, "run") == {}
    assert fmt_time(3661) == "1:01:01" and fmt_time(245.4) == "4:05"
    assert pace_str(300, "run") == "8:02 /mi" and pace_str(120, "cycle") == "30.0 km/h" and pace_str(600, "swim") == "1:00 /100m"
    rows = [
        {"id": 1, "sport": "run", "name": "a", "date": "2026-07-04", "week": "2026-06-29", "distance_m": 3000, "ascent_m": 30,
         "duration_s": 900, "avg_speed_mps": 3.33, "efforts": eff, "excluded": None},
        {"id": 2, "sport": "run", "name": "b", "date": "2026-07-11", "week": "2026-07-06", "distance_m": 6000, "ascent_m": 80,
         "duration_s": 1900, "avg_speed_mps": 3.16, "efforts": {"1 km": 250.0, "5 km": 1500.0}, "excluded": None},
        {"id": 3, "sport": "run", "name": "struck", "date": "2026-07-12", "week": "2026-07-06", "distance_m": 60000, "ascent_m": 0,
         "duration_s": 100, "avg_speed_mps": 99, "efforts": {"1 km": 1.0}, "excluded": "the car"},
    ]
    b = {(x["sport"], x["kind"], x["label"]): x for x in board(rows)}
    assert b[("run", "effort", "1 km")]["activity_id"] == 1                 # 240 beats 250; the struck 1.0 is ignored
    assert b[("run", "effort", "5 km")]["activity_id"] == 2 and b[("run", "longest", "Longest")]["activity_id"] == 2
    assert b[("run", "climb", "Most climb")]["display"] == "80 m"
    assert b[("run", "average", "Fastest average (≥ 1.9 mi)")]["activity_id"] == 1
    assert b[("all", "week", "Biggest week")]["sub"] == "week of 2026-07-06" and b[("all", "month", "Biggest month")]["display"] == "9.0 km"
    print("records: selftest OK")


if __name__ == "__main__":
    selftest()
