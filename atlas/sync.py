"""sync.py -- Garmin Connect -> data/. Fetches what is new, touches nothing that is stored.

    python -m atlas.sync            # normal run: everything since the newest stored activity
    python -m atlas.sync --since 2026-07-01   # re-open the window (stored files still win)
    python -m atlas.sync --dry-run  # list what it would fetch, write nothing

LOGIN is Argo's: GARMINTOKENS in the environment (the repository secret) or the local
.garmin_tokens/ folder that `python -m atlas.login` leaves behind. No password anywhere.

WHAT IS FETCHED. The summary from Garmin's own list (distance, ascent, duration, heart rate,
speed, cadence, calories, training effect) and, for every activity, its TCX -- the timeline of
timestamped points with the device's own cumulative distance, altitude and heart rate. The
timeline is what best efforts are computed from (the fastest 5 km inside a 12 km run is not in
any summary), so it is kept whole in data/streams/ as four parallel arrays, and a thinned
lat/lon line goes to data/tracks/ for the map. A failed TCX download stores the summary anyway.

WINDOW. From the later of HISTORY_START and the day before the newest stored activity, to today.
"""
import argparse
import datetime as dt
import os
import sys
import xml.etree.ElementTree as ET

from . import store
from .sports import sport_for
from .weeks import today_uk

HISTORY_START = dt.date(2026, 6, 1)     # Joe's watch arrived in July 2026; nothing earlier exists
TOKEN_DIR = store.ROOT / ".garmin_tokens"
TRACK_POINTS = 500
TCX_NS = "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}"


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def login():
    try:
        from garminconnect import Garmin
    except ImportError:
        sys.exit("garminconnect is not installed:  pip install garminconnect")
    tokens = os.environ.get("GARMINTOKENS")
    if tokens and len(tokens) > 512:
        api = Garmin()
        api.login(tokens)
        log("logged in from GARMINTOKENS")
        return api
    if TOKEN_DIR.exists():
        api = Garmin()
        api.login(str(TOKEN_DIR))
        log(f"logged in from {TOKEN_DIR.name}/")
        return api
    sys.exit("no Garmin tokens: run `python -m atlas.login` once, or set GARMINTOKENS")


def summary_row(a: dict) -> dict:
    """Atlas's row from a Garmin list entry. The entry itself rides along as `raw`."""
    type_key = (a.get("activityType") or {}).get("typeKey")
    return {
        "id": int(a["activityId"]),
        "name": (a.get("activityName") or "").strip(),
        "type_key": type_key,
        "sport": sport_for(type_key),
        "start_local": (a.get("startTimeLocal") or "")[:19],
        "start_gmt": (a.get("startTimeGMT") or "")[:19],
        "duration_s": a.get("duration"),
        "moving_s": a.get("movingDuration"),
        "distance_m": a.get("distance"),
        "ascent_m": a.get("elevationGain"),
        "descent_m": a.get("elevationLoss"),
        "avg_speed_mps": a.get("averageSpeed"),
        "max_speed_mps": a.get("maxSpeed"),
        "avg_hr": a.get("averageHR"),
        "max_hr": a.get("maxHR"),
        "avg_cadence": a.get("averageRunningCadenceInStepsPerMinute") or a.get("averageBikingCadenceInRevPerMinute"),
        "calories": a.get("calories"),
        "steps": a.get("steps"),
        "aerobic_te": a.get("aerobicTrainingEffect"),
        "anaerobic_te": a.get("anaerobicTrainingEffect"),
        "vo2max": a.get("vO2MaxValue"),
        "start_lat": a.get("startLatitude"),
        "start_lon": a.get("startLongitude"),
        "has_polyline": bool(a.get("hasPolyline")),
        "synced_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "raw": a,
    }


def parse_tcx(tcx: bytes) -> dict:
    """The timeline: t (seconds from the first point), d (cumulative metres, the device's own),
    alt (m), hr (bpm), and pos ([lat, lon] per point, None where the watch had no fix).
    Points without a time or distance are dropped; distance is made monotone."""
    root = ET.fromstring(tcx)
    t0 = None
    t, d, alt, hr, pos = [], [], [], [], []
    last_d = 0.0
    for tp in root.iter(f"{TCX_NS}Trackpoint"):
        time_el = tp.find(f"{TCX_NS}Time")
        dist_el = tp.find(f"{TCX_NS}DistanceMeters")
        if time_el is None or dist_el is None or time_el.text is None or dist_el.text is None:
            continue
        try:
            when = dt.datetime.fromisoformat(time_el.text.replace("Z", "+00:00"))
            dist = float(dist_el.text)
        except ValueError:
            continue
        if t0 is None:
            t0 = when
        dist = max(dist, last_d)
        last_d = dist
        t.append(round((when - t0).total_seconds(), 1))
        d.append(round(dist, 1))
        a = tp.find(f"{TCX_NS}AltitudeMeters")
        alt.append(round(float(a.text), 1) if a is not None and a.text else None)
        h = tp.find(f"{TCX_NS}HeartRateBpm/{TCX_NS}Value")
        hr.append(int(h.text) if h is not None and h.text else None)
        p = tp.find(f"{TCX_NS}Position")
        if p is not None:
            la = p.find(f"{TCX_NS}LatitudeDegrees")
            lo = p.find(f"{TCX_NS}LongitudeDegrees")
            pos.append([round(float(la.text), 5), round(float(lo.text), 5)] if la is not None and lo is not None else None)
        else:
            pos.append(None)
    return {"t": t, "d": d, "alt": alt, "hr": hr, "pos": pos}


def thin(points: list, n: int = TRACK_POINTS) -> list:
    if len(points) <= n:
        return points
    step = (len(points) - 1) / (n - 1)
    return [points[round(i * step)] for i in range(n)]


def window_start(since: str | None) -> dt.date:
    if since:
        return dt.date.fromisoformat(since)
    rows = store.activities()
    if rows:
        newest = dt.date.fromisoformat(rows[-1]["start_local"][:10])
        return max(HISTORY_START, newest - dt.timedelta(days=1))
    return HISTORY_START


def run(since: str | None = None, dry_run: bool = False) -> int:
    start, end = window_start(since), today_uk()
    api = login()
    log(f"asking Garmin for activities {start} .. {end}")
    listed = api.get_activities_by_date(str(start), str(end)) or []
    have = store.activity_ids()
    new = [a for a in listed if a.get("activityId") is not None and int(a["activityId"]) not in have]
    log(f"Garmin lists {len(listed)}; {len(new)} new")
    fetched = 0
    for a in sorted(new, key=lambda a: a.get("startTimeLocal") or ""):
        row = summary_row(a)
        km = (row["distance_m"] or 0) / 1000
        log(f"  {row['start_local'][:16]}  {row['sport']:5}  {km:5.1f} km  {row['name']}")
        if dry_run:
            continue
        try:
            from garminconnect import Garmin
            tcx = api.download_activity(row["id"], dl_fmt=Garmin.ActivityDownloadFormat.TCX)
            s = parse_tcx(tcx)
            if s["t"]:
                pos = s.pop("pos")
                line = [p for p in pos if p]
                if line:
                    store.write_track(row["id"], thin(line), len(line))
                store.write_stream(row["id"], s)
        except Exception as e:      # a missing timeline is a missing record, not a missing activity
            log(f"    TCX download failed ({e}); summary still stored")
        store.write_activity(row)
        fetched += 1
    log(f"stored {fetched} new activities" if not dry_run else "dry run -- nothing written")
    return fetched


def selftest() -> None:
    tcx = b"""<?xml version="1.0"?><TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
    <Activities><Activity Sport="Running"><Lap><Track>
      <Trackpoint><Time>2026-07-04T08:00:00Z</Time><Position><LatitudeDegrees>50.9</LatitudeDegrees><LongitudeDegrees>-1.3</LongitudeDegrees></Position>
        <AltitudeMeters>40.2</AltitudeMeters><DistanceMeters>0.0</DistanceMeters><HeartRateBpm><Value>120</Value></HeartRateBpm></Trackpoint>
      <Trackpoint><Time>2026-07-04T08:00:10Z</Time><DistanceMeters>30.5</DistanceMeters></Trackpoint>
      <Trackpoint><Time>2026-07-04T08:00:20Z</Time><DistanceMeters>25.0</DistanceMeters><HeartRateBpm><Value>130</Value></HeartRateBpm></Trackpoint>
      <Trackpoint><Time>2026-07-04T08:00:30Z</Time></Trackpoint>
    </Track></Lap></Activity></Activities></TrainingCenterDatabase>"""
    s = parse_tcx(tcx)
    assert s["t"] == [0.0, 10.0, 20.0] and s["d"] == [0.0, 30.5, 30.5], s     # monotone; the 4th point dropped
    assert s["hr"] == [120, None, 130] and s["alt"] == [40.2, None, None]
    assert s["pos"] == [[50.9, -1.3], None, None]
    assert len(thin([[i, i] for i in range(2000)])) == TRACK_POINTS
    row = summary_row({"activityId": "9", "activityType": {"typeKey": "trail_running"}, "startTimeLocal": "2026-07-04 08:00:00.0",
                       "distance": 5000.0, "averageRunningCadenceInStepsPerMinute": 172.0})
    assert row["sport"] == "run" and row["avg_cadence"] == 172.0 and row["start_local"] == "2026-07-04 08:00:00"
    print("sync: selftest OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    run(a.since, a.dry_run)


if __name__ == "__main__":
    main()
