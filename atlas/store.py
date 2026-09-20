"""store.py -- the data folder IS the database.

    data/activities/<id>.json   one per Garmin activity: Atlas's fields + the raw summary, kept whole
    data/tracks/<id>.json       the activity's line, thinned for the map (lat/lon pairs)
    data/streams/<id>.json      the activity's timeline from its TCX: parallel arrays of seconds,
                                metres, altitude and heart rate -- what the records are computed from
    data/overrides.json         Ben's/Joe's corrections  {"exclude": {"<id>": "reason"}, "sport": {"<id>": "kayak"}}

Plain JSON in git, as in Argo: every sync is a commit and GitHub Actions reads and writes it with
nothing installed. An activity file is written once and never edited (its raw summary is the
original); everything derived -- records, rankings, every chart -- is recomputed by stats.py on
every run and never stored.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ACTS = DATA / "activities"
TRACKS = DATA / "tracks"
STREAMS = DATA / "streams"
OVERRIDES = DATA / "overrides.json"
DOCS = ROOT / "docs"


def _read(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, obj, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, separators=(",", ":")) if compact else \
        json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")


def activity_ids() -> set[int]:
    return {int(p.stem) for p in ACTS.glob("*.json")}


def activities() -> list[dict]:
    """Every stored activity, oldest first."""
    rows = [_read(p, None) for p in ACTS.glob("*.json")]
    return sorted((r for r in rows if r), key=lambda r: r["start_local"])


def write_activity(row: dict) -> None:
    _write(ACTS / f"{row['id']}.json", row)


def write_track(activity_id: int, points: list[list[float]], n_raw: int) -> None:
    _write(TRACKS / f"{activity_id}.json", {"id": activity_id, "n_raw": n_raw, "points": points}, compact=True)


def has_track(activity_id: int) -> bool:
    return (TRACKS / f"{activity_id}.json").exists()


def write_stream(activity_id: int, stream: dict) -> None:
    _write(STREAMS / f"{activity_id}.json", stream, compact=True)


def stream(activity_id: int) -> dict | None:
    return _read(STREAMS / f"{activity_id}.json", None)


def overrides() -> dict:
    ov = _read(OVERRIDES, {})
    ov.setdefault("exclude", {})
    ov.setdefault("sport", {})
    return ov


def write_overrides(obj: dict) -> None:
    _write(OVERRIDES, obj)
