"""stats.py -- every number on the page, derived from data/ on every run.

    python -m atlas.stats            # writes docs/data.json (and copies the tracks) for the page
    python -m atlas.stats --print    # the headline numbers and the records, printed
    python -m atlas.stats --selftest

What goes into data.json:
  activities   every activity, scored (scoring.py), with its best efforts (records.py), pace,
               flags, and its RANK overall and within its sport
  records      the board -- fastest 1 km / 5 km / ..., longest, most climb, biggest week and month
  progression  for every (sport, target): each activity's time, and the running best -- the
               line a records chart draws
  weeks/months per sport per period: count, distance, time, climb, score
  trends       runs and rides as (date, pace or speed, avg HR, distance) for the fitness chart:
               heart rate at a pace falling over time is the real signal of getting fitter
  streaks      the current run of weeks with an activity, the longest, weeks active of weeks total
  totals       all-time, per sport, and this week against last week

Nothing is cached. The only stored state is overrides.json (strikes and sport relabels).
"""
import argparse
import datetime as dt
import json
import shutil

from . import records, scoring, store
from .weeks import this_week, today_uk, week_for, week_label, week_of

MI = records.MI


def flags_for(row: dict) -> list[str]:
    out = []
    sport = row.get("sport")
    if sport == "other":
        return [f"not a scored sport ({row.get('type_key') or 'unknown'})"]
    speed = row.get("avg_speed_mps") or 0
    ceiling = scoring.MAX_SPEED_MPS.get(sport)
    if ceiling and speed > ceiling:
        out.append(f"average speed {speed * 2.23694:.1f} mph is over the {sport} ceiling")
    if not row.get("avg_hr") and (row.get("distance_m") or 0) > 0:
        out.append("no heart rate recorded")
    if 0 < (row.get("distance_m") or 0) < scoring.MIN_DISTANCE_M:
        out.append(f"only {row['distance_m']:.0f} m")
    return out


def scored_rows(activities: list[dict], overrides: dict, streams=None) -> list[dict]:
    """One row per activity with score, efforts, pace and flags. `streams(id)` supplies the
    timeline (store.stream by default; a selftest passes its own)."""
    streams = streams or store.stream
    excluded = overrides.get("exclude", {})
    relabel = overrides.get("sport", {})
    out = []
    for a in activities:
        if not a.get("start_local"):
            continue
        if str(a["id"]) in relabel:
            a = {**a, "sport": relabel[str(a["id"])], "relabelled": True}
        ex = excluded.get(str(a["id"]))
        dist, dur = a.get("distance_m") or 0.0, a.get("duration_s") or 0.0
        sc = 0.0 if ex else scoring.score(a["sport"], dist, a.get("ascent_m"))
        eff = records.best_efforts(streams(a["id"]), a["sport"]) if not ex else {}
        spk = (dur / (dist / 1000)) if dist > 0 and dur > 0 else None      # seconds per km, from the summary
        out.append({
            "id": a["id"], "name": a["name"], "sport": a["sport"], "type_key": a.get("type_key"),
            "date": a["start_local"][:10], "start_local": a["start_local"], "week": week_for(a["start_local"]).isoformat(),
            "month": a["start_local"][:7],
            "distance_m": dist, "ascent_m": a.get("ascent_m") or 0.0, "duration_s": dur, "moving_s": a.get("moving_s"),
            "avg_hr": a.get("avg_hr"), "max_hr": a.get("max_hr"), "avg_speed_mps": a.get("avg_speed_mps"),
            "avg_cadence": a.get("avg_cadence"), "calories": a.get("calories"),
            "aerobic_te": a.get("aerobic_te"), "anaerobic_te": a.get("anaerobic_te"), "vo2max": a.get("vo2max"),
            "secs_per_km": round(spk, 1) if spk else None,
            "pace": records.pace_str(spk, a["sport"]) if spk and a["sport"] in scoring.SPORTS else None,
            "score": round(sc, 2), "efforts": eff,
            "flags": flags_for(a), "excluded": ex, "relabelled": bool(a.get("relabelled")),
            "has_track": store.has_track(a["id"]),
        })
    return out


def rank(rows: list[dict]) -> None:
    """Adds rank (all activities) and sport_rank (within the sport), 1 = best, by score; struck
    and unscored activities are unranked."""
    live = [r for r in rows if r["score"] > 0]
    for i, r in enumerate(sorted(live, key=lambda r: -r["score"]), 1):
        r["rank"] = i
    for sport in scoring.SPORTS:
        for i, r in enumerate(sorted((r for r in live if r["sport"] == sport), key=lambda r: -r["score"]), 1):
            r["sport_rank"] = i
    for r in rows:
        r.setdefault("rank", None)
        r.setdefault("sport_rank", None)


def _period(rows: list[dict], key: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in rows:
        if r["excluded"]:
            continue
        p = out.setdefault(r[key], {"n": 0, "distance_m": 0.0, "duration_s": 0.0, "ascent_m": 0.0, "score": 0.0, "sports": {}})
        p["n"] += 1
        p["distance_m"] += r["distance_m"]
        p["duration_s"] += r["duration_s"]
        p["ascent_m"] += r["ascent_m"]
        p["score"] += r["score"]
        s = p["sports"].setdefault(r["sport"], {"n": 0, "distance_m": 0.0, "duration_s": 0.0, "ascent_m": 0.0, "score": 0.0})
        s["n"] += 1
        s["distance_m"] += r["distance_m"]
        s["duration_s"] += r["duration_s"]
        s["ascent_m"] += r["ascent_m"]
        s["score"] += r["score"]
    return out


def weeks_table(rows: list[dict], first: dt.date | None) -> list[dict]:
    """Every week from the first activity to this week, oldest first, empty weeks included."""
    per = _period(rows, "week")
    out = []
    if first is None:
        return out
    monday, end = week_of(first), this_week()
    while monday <= end:
        k = monday.isoformat()
        p = per.get(k, {"n": 0, "distance_m": 0.0, "duration_s": 0.0, "ascent_m": 0.0, "score": 0.0, "sports": {}})
        out.append({"key": k, "label": week_label(monday), **_round(p)})
        monday += dt.timedelta(days=7)
    return out


def months_table(rows: list[dict]) -> list[dict]:
    per = _period(rows, "month")
    return [{"key": k, "label": dt.date.fromisoformat(k + "-01").strftime("%b %Y"), **_round(p)} for k, p in sorted(per.items())]


def _round(p: dict) -> dict:
    q = {k: (round(v, 1) if isinstance(v, float) else v) for k, v in p.items() if k != "sports"}
    q["sports"] = {s: {k: (round(v, 1) if isinstance(v, float) else v) for k, v in d.items()} for s, d in p["sports"].items()}
    return q


def progression(rows: list[dict]) -> dict[str, list[dict]]:
    """{ "run|5 km": [{date, seconds, activity_id, best}, ...] } oldest first; `best` is the
    running record at that point, so the chart can draw attempts as dots and the record as a line."""
    out: dict[str, list[dict]] = {}
    for r in sorted(rows, key=lambda r: r["start_local"]):
        if r["excluded"]:
            continue
        for label, secs in r["efforts"].items():
            key = f"{r['sport']}|{label}"
            series = out.setdefault(key, [])
            best = min(secs, series[-1]["best"]) if series else secs
            series.append({"date": r["date"], "seconds": secs, "activity_id": r["id"], "best": best,
                           "improved": not series or secs < series[-1]["best"]})
    return out


def streaks(weeks: list[dict]) -> dict:
    cur = longest = run = 0
    active = 0
    for w in weeks:
        if w["n"] > 0:
            run += 1
            active += 1
            longest = max(longest, run)
        else:
            run = 0
    # the current streak counts back from this week, allowing this week to still be empty
    for w in reversed(weeks[:-1] if weeks and weeks[-1]["n"] == 0 else weeks):
        if w["n"] > 0:
            cur += 1
        else:
            break
    return {"current": cur, "longest": longest, "weeks_active": active, "weeks_total": len(weeks)}


def build(activities: list[dict] | None = None, overrides: dict | None = None, streams=None) -> dict:
    activities = store.activities() if activities is None else activities
    overrides = store.overrides() if overrides is None else overrides
    rows = scored_rows(activities, overrides, streams)
    rank(rows)
    first = dt.date.fromisoformat(min(r["date"] for r in rows)) if rows else None
    weeks = weeks_table(rows, first)
    months = months_table(rows)
    live = [r for r in rows if not r["excluded"]]
    totals = {"n": len(live), "distance_m": round(sum(r["distance_m"] for r in live), 1),
              "duration_s": round(sum(r["duration_s"] for r in live)), "ascent_m": round(sum(r["ascent_m"] for r in live)),
              "score": round(sum(r["score"] for r in live), 1),
              "sports": {s: {"n": sum(1 for r in live if r["sport"] == s),
                             "distance_m": round(sum(r["distance_m"] for r in live if r["sport"] == s), 1),
                             "duration_s": round(sum(r["duration_s"] for r in live if r["sport"] == s)),
                             "ascent_m": round(sum(r["ascent_m"] for r in live if r["sport"] == s))}
                         for s in scoring.SPORTS if any(r["sport"] == s for r in live)}}
    tw = this_week().isoformat()
    lw = (this_week() - dt.timedelta(days=7)).isoformat()
    by_week = {w["key"]: w for w in weeks}
    trends = {
        "run": [{"date": r["date"], "secs_per_km": r["secs_per_km"], "hr": r["avg_hr"], "distance_m": r["distance_m"], "id": r["id"]}
                for r in live if r["sport"] == "run" and r["secs_per_km"] and r["distance_m"] >= 1000],
        "cycle": [{"date": r["date"], "kmh": round(r["avg_speed_mps"] * 3.6, 1), "hr": r["avg_hr"], "distance_m": r["distance_m"], "id": r["id"]}
                  for r in live if r["sport"] == "cycle" and r.get("avg_speed_mps") and r["distance_m"] >= 3000],
    }
    rows.sort(key=lambda r: r["start_local"], reverse=True)
    return {
        "built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "today": today_uk().isoformat(),
        "name": "Joe",
        "targets": {s: [[round(m, 1), lab] for m, lab in ladder] for s, ladder in records.TARGETS.items()},
        "since": first.isoformat() if first else None,
        "totals": totals,
        "this_week": by_week.get(tw), "last_week": by_week.get(lw),
        "streaks": streaks(weeks),
        "records": records.board(rows),
        "progression": progression(rows),
        "weeks": weeks, "months": months,
        "trends": trends,
        "activities": rows,
    }


def write_site(data: dict) -> bool:
    store.DOCS.mkdir(exist_ok=True)
    target = store.DOCS / "data.json"
    if target.exists():
        try:
            old = json.loads(target.read_text(encoding="utf-8"))
            strip = lambda d: {k: v for k, v in d.items() if k not in ("built_at", "today")}   # noqa: E731
            if strip(old) == strip(data):
                return False
        except ValueError:
            pass
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    dest = store.DOCS / "tracks"
    dest.mkdir(exist_ok=True)
    wanted = {f"{r['id']}.json" for r in data["activities"] if r["has_track"]}
    for p in dest.glob("*.json"):
        if p.name not in wanted:
            p.unlink()
    for name in wanted:
        src = store.TRACKS / name
        if src.exists():
            shutil.copyfile(src, dest / name)
    return True


def print_report(data: dict) -> None:
    t = data["totals"]
    print(f"Atlas -- {t['n']} activities since {data['since']}, {t['distance_m'] / 1000:.1f} km, "
          f"{t['ascent_m']} m climbed, {records.fmt_time(t['duration_s'])} moving; streak {data['streaks']['current']} weeks "
          f"(longest {data['streaks']['longest']}, active {data['streaks']['weeks_active']}/{data['streaks']['weeks_total']})")
    for s, v in t["sports"].items():
        print(f"  {s:5} {v['n']:3}  {v['distance_m'] / 1000:7.1f} km  {v['ascent_m']:5} m  {records.fmt_time(v['duration_s'])}")
    print("records:")
    for r in data["records"]:
        print(f"  {r['sport']:5} {r['label']:32} {r['display']:>10}  {r.get('sub', ''):14} {r['date']}  {r.get('name', '')}")
    print("top 10 by score:")
    for r in sorted((r for r in data["activities"] if r["rank"]), key=lambda r: r["rank"])[:10]:
        print(f"  #{r['rank']:<3} {r['date']}  {r['sport']:5} {r['distance_m'] / 1000:6.1f} km {r['ascent_m']:5.0f} m  {r['score']:6.1f}  {r['name']}")


def selftest() -> None:
    t, d = [0.0], [0.0]
    for i in range(1, 601):
        d.append(i * 10.0)
        t.append(t[-1] + (0.25 if 2000 <= i * 10 <= 3000 else 0.30) * 10)
    streams = {1: {"t": t, "d": d}, 2: None, 3: {"t": [0, 100], "d": [0, 400]}}
    acts = [
        {"id": 1, "name": "Tempo", "sport": "run", "type_key": "running", "start_local": "2026-07-06 07:00:00",
         "distance_m": 6000, "ascent_m": 40, "duration_s": 1770, "avg_hr": 155, "avg_speed_mps": 3.39},
        {"id": 2, "name": "Ride", "sport": "cycle", "type_key": "cycling", "start_local": "2026-07-14 17:00:00",
         "distance_m": 30000, "ascent_m": 300, "duration_s": 4000, "avg_hr": 140, "avg_speed_mps": 7.5},
        {"id": 3, "name": "Splash", "sport": "swim", "type_key": "lap_swimming", "start_local": "2026-07-15 07:00:00",
         "distance_m": 400, "ascent_m": 0, "duration_s": 100, "avg_hr": None, "avg_speed_mps": 1.0},
        {"id": 4, "name": "Car", "sport": "cycle", "type_key": "cycling", "start_local": "2026-07-16 17:00:00",
         "distance_m": 50000, "ascent_m": 0, "duration_s": 1000, "avg_hr": 90, "avg_speed_mps": 50},
    ]
    dd = build(acts, {"exclude": {"4": "the car"}, "sport": {}}, streams=lambda i: streams.get(i))
    rows = {r["id"]: r for r in dd["activities"]}
    assert rows[1]["rank"] == 2 and rows[2]["rank"] == 1 and rows[2]["sport_rank"] == 1 and rows[1]["sport_rank"] == 1
    assert rows[4]["rank"] is None and rows[4]["score"] == 0 and rows[4]["efforts"] == {}
    assert {"400 m", "1 km", "1 mile", "5 km", "2 miles"} <= set(rows[1]["efforts"]) and abs(rows[1]["efforts"]["1 km"] - 250) < 1
    assert "5 miles" not in rows[1]["efforts"] and dd["targets"]["run"][0] == [400, "400 m"]
    assert rows[1]["pace"] == "7:54 /mi" and rows[3]["flags"] == ["no heart rate recorded"]
    assert any("over the cycle ceiling" in f for f in rows[4]["flags"])
    rec = {(r["sport"], r["label"]): r for r in dd["records"]}
    assert rec[("run", "5 km")]["activity_id"] == 1 and rec[("cycle", "Longest")]["activity_id"] == 2   # the struck 50 km is not longest
    assert rec[("swim", "400 m")]["display"] == "1:40"
    assert dd["progression"]["run|1 km"][0]["improved"] is True
    assert dd["totals"]["n"] == 3 and dd["totals"]["sports"]["cycle"]["distance_m"] == 30000
    assert dd["weeks"][0]["key"] == "2026-07-06" and dd["weeks"][0]["n"] == 1 and dd["weeks"][1]["n"] == 2
    assert dd["months"][0]["key"] == "2026-07" and dd["months"][0]["n"] == 3
    st = dd["streaks"]
    assert st["longest"] == 2 and st["weeks_active"] == 2
    assert len(dd["trends"]["run"]) == 1 and dd["trends"]["cycle"][0]["kmh"] == 27.0
    assert build([], {"exclude": {}, "sport": {}})["records"] == []
    print("stats: selftest OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--print", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    data = build()
    changed = write_site(data)
    if a.print:
        print_report(data)
    print(f"docs/data.json {'written' if changed else 'unchanged'}: {data['totals']['n']} activities, {len(data['records'])} records")


if __name__ == "__main__":
    main()
