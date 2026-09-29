"""frontiers.py -- the congratulations: one message for every activity that moved a frontier.

Ben, 29/09/2026: "add some congratulatory messages to Joe that are revealed when he hits a new
record, longest walk, fastest 5k etc, only 1 message per activity, the most relevant whenever a
frontier is moved."

`messages(rows)` replays the activities OLDEST FIRST, carrying every frontier the records board
shows -- the fastest time at each rung of the ladder, the longest, the most climb, the longest
time, the fastest average, the biggest week and month -- plus the longest streak. Everything an
activity moved when it happened is a candidate; the most relevant one becomes its message and the
rest are one line under it. An activity that moved nothing has no message. Struck activities are
not replayed at all, so they neither earn a message nor set the bar for one. Nothing is stored:
strike an old activity and the messages after it re-derive on the next run.

Most relevant, in order (`ORDER`):
  1. the first activity of a sport -- everything on its board is new, so nothing else is said;
  2. a MILESTONE, the first time over a named distance (`MILESTONES`: the first 5 km run, the
     first half marathon, the first 100 km ride ...), the longest one crossed;
  3. then the sport decides. Running and swimming are about speed, so a PB comes next, then the
     longest; walking, cycling and paddling are about distance, so the longest comes next, then
     the most climb, then a PB. A PB is chosen by BARRIER first (under 30 minutes for 5 km is the
     moment a runner remembers, `BARRIERS`), then by the longest rung: long rungs are what he
     would quote and the least at the mercy of a GPS wobble;
  4. the fastest average, the most climb, the longest time, the biggest week, the biggest month,
     the longest streak.

A week, month or streak record goes to the activity that CROSSED the old best, not to every one
after it in the same week. The very first week, month and streak are not records -- there was
nothing to beat.

The words are content, written here; `_pick` varies them by activity id so the same activity
always reads the same.
"""
import datetime as dt

from . import records, scoring
from .records import fmt_time, pace_str

NOUN = {"run": "run", "walk": "walk", "cycle": "ride", "swim": "swim", "kayak": "paddle"}
DONE = {"run": "run", "walk": "walked", "cycle": "ridden", "swim": "swum", "kayak": "paddled"}
STYLE = {"run": "speed", "swim": "speed", "walk": "distance", "cycle": "distance", "kayak": "distance"}
ORDER = {
    "speed":    ["first_sport", "milestone", "pb", "longest", "average", "climb", "duration", "week", "month", "streak"],
    "distance": ["first_sport", "milestone", "longest", "climb", "pb", "average", "duration", "week", "month", "streak"],
}
SPINNAKER_M = 170       # the Spinnaker Tower, Portsmouth -- a climb's yardstick once there is one to use

M_ = 60
H_ = 3600
# round times a PB can go UNDER, per (sport, rung), in seconds
BARRIERS = {
    ("run", "1 km"): [6 * M_, 5 * M_, 4 * M_],
    ("run", "1 mile"): [10 * M_, 9 * M_, 8 * M_, 7 * M_, 6 * M_, 5 * M_],
    ("run", "5 km"): [40 * M_, 35 * M_, 30 * M_, 25 * M_, 20 * M_, 18 * M_, 16 * M_],
    ("run", "5 miles"): [60 * M_, 50 * M_, 45 * M_, 40 * M_, 35 * M_, 30 * M_],
    ("run", "10 km"): [80 * M_, 70 * M_, 60 * M_, 55 * M_, 50 * M_, 45 * M_, 40 * M_, 35 * M_],
    ("run", "10 miles"): [2 * H_, 105 * M_, 90 * M_, 80 * M_, 75 * M_, 70 * M_, 65 * M_, H_],
    ("run", "Half marathon"): [150 * M_, 135 * M_, 2 * H_, 110 * M_, 105 * M_, 100 * M_, 90 * M_, 80 * M_],
    ("run", "Marathon"): [5 * H_, 270 * M_, 4 * H_, 225 * M_, 210 * M_, 195 * M_, 3 * H_],
    ("cycle", "10 km"): [40 * M_, 30 * M_, 25 * M_, 20 * M_, 17 * M_],
    ("cycle", "20 km"): [80 * M_, H_, 50 * M_, 40 * M_],
    ("cycle", "40 km"): [160 * M_, 2 * H_, 100 * M_, 90 * M_, 80 * M_, 70 * M_, H_],
    ("cycle", "50 km"): [200 * M_, 150 * M_, 2 * H_, 105 * M_, 100 * M_, 90 * M_],
    ("cycle", "100 km"): [400 * M_, 5 * H_, 4 * H_, 210 * M_, 200 * M_, 3 * H_],
    ("cycle", "100 miles"): [10 * H_, 8 * H_, 7 * H_, 6 * H_, 5 * H_],
    ("walk", "1 mile"): [20 * M_, 17 * M_, 15 * M_, 13 * M_, 12 * M_],
    ("walk", "5 km"): [H_, 50 * M_, 45 * M_, 40 * M_],
    ("walk", "10 km"): [2 * H_, 105 * M_, 100 * M_, 90 * M_],
    ("swim", "100 m"): [3 * M_, 150, 2 * M_, 105, 90, 80, 70, M_],
    ("swim", "400 m"): [12 * M_, 10 * M_, 9 * M_, 8 * M_, 7 * M_, 6 * M_],
    ("swim", "1 km"): [30 * M_, 25 * M_, 20 * M_, 18 * M_, 16 * M_, 15 * M_],
    ("swim", "1 mile"): [50 * M_, 45 * M_, 40 * M_, 35 * M_, 30 * M_, 25 * M_],
    ("kayak", "1 km"): [10 * M_, 8 * M_, 7 * M_, 6 * M_, 5 * M_],
    ("kayak", "5 km"): [50 * M_, 40 * M_, 35 * M_, 30 * M_],
    ("kayak", "10 km"): [100 * M_, 80 * M_, 70 * M_, H_],
}

# the named distances: (sport, rung) -> (title, message). {rtime} is the time for the distance.
MILESTONES = {
    ("run", "5 km"): ("First 5 km run",
        "Five kilometres in one run — {rtime} for the distance. That's parkrun: every Saturday morning, all over "
        "the country, this is the one people line up for. You're one of them now."),
    ("run", "5 miles"): ("First 5-mile run",
        "Five miles in one run, Joe. {rtime} for the five. That's well past the point where most people would "
        "have stopped, and you kept going."),
    ("run", "10 km"): ("First 10 km run",
        "Your first 10 km run. {rtime} for the ten — a proper race distance, the kind with a medal at the end."),
    ("run", "10 miles"): ("First 10-mile run",
        "Ten miles running, in one go. That's the Great South Run — the whole of it — in {rtime}."),
    ("run", "Half marathon"): ("First half marathon",
        "A half marathon. 13.1 miles in one run, {rtime} for the distance. Most people never run one in their lives."),
    ("run", "30 km"): ("First 30 km run",
        "Thirty kilometres. You're past the half and into the country where marathons are made. {rtime} for the 30."),
    ("run", "Marathon"): ("First marathon",
        "A MARATHON. 26.2 miles, {rtime}. There is no bigger number on the running board. Sit down, Joe. "
        "You've earned the sofa."),
    ("cycle", "20 miles"): ("First 20-mile ride",
        "Twenty miles on the bike in one ride — {rtime} for the twenty. That's a proper day out, not a spin round the block."),
    ("cycle", "50 km"): ("First 50 km ride",
        "Fifty kilometres in one ride. {rtime} for the fifty. Your legs have officially left the local area."),
    ("cycle", "50 miles"): ("First 50-mile ride",
        "Fifty miles in the saddle, {rtime} for the distance. Cyclists call this a half century, and they don't "
        "hand that name out lightly."),
    ("cycle", "100 km"): ("First 100 km ride",
        "A hundred kilometres in one ride — a metric century. {rtime} for the hundred. Club riders plan whole "
        "Sundays round this distance."),
    ("cycle", "100 miles"): ("First century",
        "A HUNDRED MILES. The century — the ride every cyclist measures themselves against — in {rtime}. "
        "That one goes on the wall, Joe."),
    ("walk", "5 miles"): ("First 5-mile walk",
        "Five miles walked in one go — {rtime} for the five. That's a proper walk, not a wander, and the record's yours."),
    ("walk", "10 km"): ("First 10 km walk",
        "Ten kilometres on foot, {rtime} for the ten. That's a real hike — the kind people pack a lunch for."),
    ("walk", "10 miles"): ("First 10-mile walk",
        "Ten miles walking in one day out. {rtime} for the ten. That's most of a day on the hills, and you did the lot."),
    ("walk", "20 km"): ("First 20 km walk",
        "Twenty kilometres walked in one go. Your feet may be filing a complaint; the records board is not. "
        "{rtime} for the twenty."),
    ("swim", "400 m"): ("First 400 m swim",
        "400 m in one swim — sixteen lengths of a 25 m pool. {rtime} for the four hundred."),
    ("swim", "1 km"): ("First 1 km swim",
        "A kilometre swum. Forty lengths of a 25 m pool, {rtime}. That's a real swim."),
    ("swim", "1 mile"): ("First mile swim",
        "A mile in the water. {rtime}. That's the distance open-water swimmers train in, Joe — and you've done it."),
    ("kayak", "5 km"): ("First 5 km paddle",
        "Five kilometres paddled in one go — {rtime} for the five. The water's a long way from the car park now."),
    ("kayak", "10 km"): ("First 10 km paddle",
        "Ten kilometres on the water, {rtime} for the ten. Your shoulders will tell you about this one tomorrow."),
}

FIRST = {
    "run": ("First run", "Your first run on the watch: {dist} in {time}{rung}. Every running record on the board "
            "belongs to this one now — which makes every one of them a target."),
    "walk": ("First walk", "Your first walk on the watch: {dist} in {time}. The walking board opens here, Joe. "
             "From now on, every walk is up against this one."),
    "cycle": ("First ride", "Your first ride on the watch: {dist} in {time}{climb}. That's the cycling board "
              "opened — every ride from here is racing this one."),
    "swim": ("First swim", "Your first swim on the watch: {dist}. The swimming records start here. Water is the "
             "hardest place to find speed, so every second off these is earned."),
    "kayak": ("First paddle", "Your first paddle on the watch: {dist} in {time}. Most people's kayaking records "
              "don't exist at all. Yours do now."),
}

PB = [
    "{time}, {margin} faster than your old best of {old}. That's {pace}, and it's the new mark to beat.",
    "New {label} record, Joe — {time}. The old one stood for {age}; you took {margin} off it.",
    "{time} for {label}. That's {margin} faster than you've ever covered it before — the record line on the "
    "chart just stepped down.",
    "The {label} record falls: {old} to {time}. {margin} found from somewhere.",
]
PB_BARRIER = [
    "{time} for {label} — {margin} faster than your old best of {old}, and under {phrase} for the first time. "
    "That's a barrier, not just a number, and it stays broken.",
    "{time} for {label}. You're officially under {phrase} now, Joe — {pace} the whole way. Nobody can take "
    "that back off you.",
]
LONGEST = [
    "{dist}, beating your old best of {old}. The edge of the map just moved.",
    "{dist} — the furthest you've ever {done} in one go, Joe. The old longest was {old}.",
    "New longest {noun}: {dist} in {time}. That's {pct} further than anything before it.",
]
LONGEST_JUST = ["Only just: {dist}, {extra} further than the old best. A record is a record."]
CLIMB = [
    "{climb} m of climbing in one {noun}, beating {old} m. Gravity lost this one.",
    "{climb} m of up — the most you've ever climbed in one {noun}, Joe. The old best was {old} m.",
]
CLIMB_TOWERS = ["{climb} m of up — the most you've ever climbed in one {noun}, Joe. That's {towers} Spinnaker "
                "Towers stacked on top of each other."]
CLIMB_FIRST = ["The first real climbing on the {noun} board: {climb} m of up. Gravity lost this one."]
DURATION = [
    "{time} out there, beating {old}. Stamina is a record too.",
    "{time} on the go — your longest {noun} yet, Joe. Endurance is mostly not stopping, and you didn't.",
]
AVERAGE = [
    "{pace} over {dist}, beating {old}. Not one quick stretch — the whole thing.",
    "{pace} for the whole {noun}, start to finish. That's your best average ever over {floor} or more, Joe.",
]
WEEK = [
    "This {noun} took the week to {km} km, past your old best of {old} km.",
    "{km} km this week and counting — more than any week before it. This {noun} is the one that tipped it over.",
]
MONTH = [
    "This {noun} took {month} to {km} km, past your old best of {old} km.",
    "{month} just became your biggest month — {km} km and counting, past {old} km.",
]
STREAK = [
    "{n} weeks in a row with at least one session — your longest streak yet. Consistency is the stat that "
    "moves all the others.",
    "That's {n} weeks on the trot, Joe. The longest streak you've ever had. Keep the chain going.",
]


def _pick(variants: list[str], aid) -> str:
    return variants[int(aid) % len(variants)]


def _the(label: str) -> str:
    return "the " + label.lower() if label in ("Half marathon", "Marathon") else label


def _under(secs: float) -> str:
    """A barrier in words: 30 minutes, 1:45, 2 hours, 1:30 (for 90 s)."""
    s = int(secs)
    if s < H_:
        return f"{s // M_} minutes" if s % M_ == 0 else f"{s // M_}:{s % M_:02d}"
    if s % H_ == 0:
        return f"{s // H_} hour" + ("s" if s > H_ else "")
    return f"{s // H_}:{s % H_ // M_:02d}"


def _margin(secs: float) -> str:
    if secs < 1:
        return "less than a second"
    if secs < 60:
        n = int(round(secs))
        return f"{n} second" + ("s" if n != 1 else "")
    return fmt_time(secs)


def _age(since: str, until: str) -> str:
    n = (dt.date.fromisoformat(until) - dt.date.fromisoformat(since)).days
    if n < 1:
        return "less than a day"
    if n == 1:
        return "a day"
    if n < 14:
        return f"{n} days"
    if n < 60:
        return f"{n // 7} weeks"
    return f"{n // 30} months"


def _km(m: float) -> str:
    return f"{m / 1000:.1f}"


def _streak_ending(active: set, monday: dt.date) -> int:
    n = 0
    while monday in active:
        n += 1
        monday -= dt.timedelta(days=7)
    return n


def messages(rows: list[dict]) -> dict:
    """{activity id: {key, kind, title, text, also, also_n}} for every activity that moved a
    frontier. `rows` are stats.py's scored rows (efforts attached); order does not matter."""
    live = sorted((r for r in rows if not r.get("excluded")), key=lambda r: r["start_local"])
    eff: dict[tuple, tuple] = {}          # (sport, label) -> (seconds, date)
    best: dict[tuple, tuple] = {}         # (sport, kind) -> (value, date)
    weeks: dict[str, float] = {}
    months: dict[str, float] = {}
    active: set = set()
    longest_streak = 0
    out = {}
    for r in live:
        sport, aid = r["sport"], r["id"]
        dist, climb, dur = r.get("distance_m") or 0.0, r.get("ascent_m") or 0.0, r.get("duration_s") or 0.0
        speed = r.get("avg_speed_mps") or 0.0
        floor = records.AVG_FLOOR_M.get(sport, 0)
        real = sport in scoring.SPORTS
        cands = []
        first = real and not any(k[0] == sport for k in best)
        # --- this activity's own frontiers -----------------------------------------------------
        if real and not first:
            for metres, label in records.TARGETS.get(sport, []):
                secs = r["efforts"].get(label)
                if secs is None:
                    continue
                prev = eff.get((sport, label))
                if prev is None:
                    kind = "milestone" if (sport, label) in MILESTONES else "rung"
                    cands.append({"kind": kind, "label": label, "metres": metres, "value": secs})
                elif secs < prev[0]:
                    crossed = [b for b in BARRIERS.get((sport, label), []) if prev[0] >= b > secs]
                    cands.append({"kind": "pb", "label": label, "metres": metres, "value": secs, "old": prev[0],
                                  "since": prev[1], "barrier": min(crossed) if crossed else None})
            for kind, value, ok in (("longest", dist, dist > 0), ("climb", climb, climb > 0 and sport != "swim"),
                                    ("duration", dur, dur > 0), ("average", speed, speed > 0 and dist >= floor)):
                prev = best.get((sport, kind))
                if ok and prev is not None and value > prev[0]:
                    cands.append({"kind": kind, "value": value, "old": prev[0]})
        # --- the frontiers across activities ---------------------------------------------------
        wk, mo = r["week"], r["month"]
        for kind, table, key in (("week", weeks, wk), ("month", months, mo)):
            before = table.get(key, 0.0)
            others = [v for k, v in table.items() if k != key]
            old = max(others) if others else 0.0
            table[key] = before + dist
            if old > 0 and before <= old < table[key]:
                cands.append({"kind": kind, "value": table[key], "old": old, "key": key})
        monday = dt.date.fromisoformat(wk)
        if monday not in active:
            active.add(monday)
            run = _streak_ending(active, monday)
            if longest_streak and run > longest_streak:
                cands.append({"kind": "streak", "value": run, "old": longest_streak})
            longest_streak = max(longest_streak, run)
        # --- the one message --------------------------------------------------------------------
        if real and first:
            out[aid] = _first_message(r)
        elif real and cands:
            out[aid] = _choose(r, cands)
        # --- move the frontiers ------------------------------------------------------------------
        if real:
            for label, secs in r["efforts"].items():
                if (sport, label) not in eff or secs < eff[(sport, label)][0]:
                    eff[(sport, label)] = (secs, r["date"])
            for kind, value, ok in (("longest", dist, True), ("climb", climb, sport != "swim"),
                                    ("duration", dur, True), ("average", speed, speed > 0 and dist >= floor)):
                if ok and ((sport, kind) not in best or value > best[(sport, kind)][0]):
                    best[(sport, kind)] = (value, r["date"])
    return out


def _rank(c: dict, style: str) -> tuple:
    """Smaller is more relevant: the kind's place in the sport's ORDER, then within the kind."""
    order = ORDER[style]
    k = c["kind"]
    place = order.index(k) if k in order else len(order)
    if k == "pb":
        return (place, 0 if c["barrier"] else 1, -c["metres"])
    if k == "milestone":
        return (place, 0, -c["metres"])
    return (place, 0, 0)


def _first_message(r: dict) -> dict:
    sport = r["sport"]
    title, text = FIRST[sport]
    covered = [(m, lab) for m, lab in records.TARGETS.get(sport, []) if lab in r["efforts"] and m >= 1000]
    rung = f", with {covered[-1][1]} in {fmt_time(r['efforts'][covered[-1][1]])} on the way" if covered else ""
    climb = f" and {r['ascent_m']:.0f} m of climbing" if (r.get("ascent_m") or 0) >= 1 else ""
    return {"key": f"first_sport|{sport}", "kind": "first_sport", "title": title,
            "text": text.format(dist=records._dist(r["distance_m"] or 0, sport), time=fmt_time(r["duration_s"] or 0),
                                rung=rung, climb=climb),
            "also": None, "also_n": 0}


def _choose(r: dict, cands: list[dict]) -> dict:
    style = STYLE[r["sport"]]
    ranked = sorted(cands, key=lambda c: _rank(c, style))
    top, rest = ranked[0], ranked[1:]
    title, text = _words(r, top)
    return {"key": f"{top['kind']}|{top.get('label', '')}", "kind": top["kind"], "title": title, "text": text,
            "also": _also(r, rest), "also_n": len(rest)}


def _words(r: dict, c: dict) -> tuple[str, str]:
    sport, aid, k = r["sport"], r["id"], c["kind"]
    noun = NOUN[sport]
    dist = records._dist(r["distance_m"] or 0, sport)
    if k == "milestone":
        title, text = MILESTONES[(sport, c["label"])]
        return title, text.format(rtime=fmt_time(c["value"]))
    if k == "pb":
        f = {"label": c["label"], "the_label": _the(c["label"]), "time": fmt_time(c["value"]), "old": fmt_time(c["old"]),
             "margin": _margin(c["old"] - c["value"]), "pace": pace_str(c["value"] / (c["metres"] / 1000), sport),
             "age": _age(c["since"], r["date"])}
        if c["barrier"]:
            f["phrase"] = _under(c["barrier"])
            return f"Under {f['phrase']} for {_the(c['label'])}", _pick(PB_BARRIER, aid).format(**f)
        return f"Fastest {c['label']} yet", _pick(PB, aid).format(**f)
    if k == "longest":
        pct = 100 * (c["value"] - c["old"]) / c["old"] if c["old"] else 100
        f = {"noun": noun, "dist": dist, "old": records._dist(c["old"], sport), "done": DONE[sport],
             "time": fmt_time(r["duration_s"] or 0), "pct": f"{pct:.0f}%", "extra": f"{c['value'] - c['old']:.0f} m"}
        return f"Longest {noun} yet", _pick(LONGEST_JUST if pct < 1 else LONGEST, aid).format(**f)
    if k == "climb":
        f = {"noun": noun, "climb": f"{c['value']:.0f}", "old": f"{c['old']:.0f}", "towers": f"{c['value'] / SPINNAKER_M:.1f}"}
        variants = CLIMB_FIRST if c["old"] < 1 else CLIMB + (CLIMB_TOWERS if c["value"] >= SPINNAKER_M else [])
        return "Most climb yet", _pick(variants, aid).format(**f)
    if k == "duration":
        f = {"noun": noun, "time": fmt_time(c["value"]), "old": fmt_time(c["old"])}
        return f"Longest {noun} by the clock", _pick(DURATION, aid).format(**f)
    if k == "average":
        f = {"noun": noun, "pace": pace_str(1000 / c["value"], sport), "old": pace_str(1000 / c["old"], sport), "dist": dist,
             "floor": records._dist(records.AVG_FLOOR_M.get(sport, 0), sport)}
        return f"Fastest average {noun}", _pick(AVERAGE, aid).format(**f)
    if k == "week":
        return "Biggest week yet", _pick(WEEK, aid).format(noun=noun, km=_km(c["value"]), old=_km(c["old"]))
    if k == "month":
        month = dt.date.fromisoformat(c["key"] + "-01").strftime("%B")
        return "Biggest month yet", _pick(MONTH, aid).format(noun=noun, km=_km(c["value"]), old=_km(c["old"]), month=month)
    if k == "streak":
        return "Longest streak yet", _pick(STREAK, aid).format(n=c["value"])
    raise ValueError(f"no words for {k}")


def _also(r: dict, rest: list[dict]) -> str | None:
    """The other frontiers this activity moved, as one line: 'fastest 400 m, 800 m and 1 km; longest run'."""
    if not rest:
        return None
    noun = NOUN[r["sport"]]
    parts = []
    by_kind: dict[str, list[dict]] = {}
    for c in rest:
        by_kind.setdefault(c["kind"], []).append(c)
    for kind, word in (("milestone", "first"), ("rung", "first"), ("pb", "fastest")):
        cs = sorted(by_kind.pop(kind, []), key=lambda c: c["metres"])
        if cs:
            labels = [c["label"] for c in cs]
            parts.append(f"{word} " + (labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]))
    words = {"longest": f"longest {noun}", "climb": "most climb", "duration": "longest by the clock",
             "average": "fastest average", "week": "biggest week", "month": "biggest month"}
    for kind in ("longest", "climb", "duration", "average", "week", "month", "streak"):
        for c in by_kind.pop(kind, []):
            parts.append(f"longest streak ({c['value']} weeks)" if kind == "streak" else words[kind])
    # "first 5 km" and "first 5 miles" merge into one "first ..." when both kinds are present
    firsts = [p for p in parts if p.startswith("first ")]
    if len(firsts) == 2:
        parts = [p for p in parts if not p.startswith("first ")]
        parts.insert(0, firsts[0] + ", " + firsts[1][len("first "):])
    return "; ".join(parts)


def selftest() -> None:
    def row(aid, sport, date, dist, climb=0.0, dur=1000.0, speed=None, efforts=None, excluded=None):
        d = dt.date.fromisoformat(date)
        return {"id": aid, "sport": sport, "start_local": date + " 09:00:00", "date": date, "month": date[:7],
                "week": (d - dt.timedelta(days=d.weekday())).isoformat(), "distance_m": dist, "ascent_m": climb,
                "duration_s": dur, "avg_speed_mps": speed if speed is not None else dist / dur,
                "efforts": efforts or {}, "excluded": excluded}
    rows = [
        row(1, "run", "2026-07-06", 5600, 30, 2400, efforts={"1 km": 400, "1 mile": 650, "3 km": 1200, "5 km": 2080}),
        # a PB at every rung and 2 m further: the longest rung's PB wins, and the rest are one line
        row(2, "run", "2026-07-08", 5602, 20, 2300, efforts={"1 km": 390, "1 mile": 640, "3 km": 1150, "5 km": 2000}),
        # slower everywhere, shorter, the same week: nothing moved, no message
        row(3, "run", "2026-07-09", 4000, 10, 2000, efforts={"1 km": 420, "1 mile": 700, "3 km": 1300}),
        # struck: faster than anything, and it must neither get a message nor set the bar
        row(4, "run", "2026-07-10", 9000, 0, 1000, efforts={"1 km": 100, "5 km": 900}, excluded="the car"),
        # under 30 minutes for 5 km beats a longer rung's plain PB; the first 5 miles beats both
        row(5, "run", "2026-07-15", 5000, 20, 1790, efforts={"1 km": 380, "1 mile": 630, "3 km": 1100, "5 km": 1790}),
        row(6, "run", "2026-07-20", 8100, 20, 3000, efforts={"1 km": 370, "5 km": 1780, "5 miles": 2950}),
        row(7, "walk", "2026-07-21", 5000, 0, 3600, efforts={"1 mile": 1200, "5 km": 3600}),
        # a walk: the longest walk outranks a 1 mile PB
        row(8, "walk", "2026-07-22", 6000, 0, 4000, efforts={"1 mile": 1150, "5 km": 3500}),
        row(9, "walk", "2026-08-03", 5500, 400, 5000, efforts={"1 mile": 1300, "5 km": 3700}),
    ]
    m = messages(rows)
    assert m[1]["kind"] == "first_sport" and m[1]["also"] is None and "5 km in 34:40 on the way" in m[1]["text"], m[1]
    assert m[2]["kind"] == "pb" and m[2]["key"] == "pb|5 km" and m[2]["title"] == "Fastest 5 km yet", m[2]
    assert m[2]["also"] == "fastest 1 km, 1 mile and 3 km; longest run; fastest average" and m[2]["also_n"] == 5, m[2]
    assert 3 not in m and 4 not in m
    assert m[5]["kind"] == "pb" and m[5]["title"] == "Under 30 minutes for 5 km", m[5]   # 2000 -> 1790 crosses 30:00
    assert "1:30" in _under(90) and _under(105 * M_) == "1:45" and _under(2 * H_) == "2 hours" and _under(H_) == "1 hour"
    assert m[6]["kind"] == "milestone" and m[6]["title"] == "First 5-mile run" and "49:10" in m[6]["text"], m[6]
    assert m[7]["kind"] == "first_sport" and m[8]["kind"] == "longest", m[8]
    # a walk: the longest walk outranks two PBs; the week of 20 July (19.1 km) crosses 6 July's 15.2 km here
    assert m[8]["also"] == "fastest 1 mile and 5 km; longest by the clock; fastest average; biggest week", m[8]
    # most climb from nothing reads as the first climbing, not "beating 0 m"
    assert m[9]["kind"] == "climb" and m[9]["text"].startswith("The first real climbing"), m[9]
    assert m[9]["also"] == "longest by the clock", m[9]
    # a streak: weekly walks, each shorter than the last so nothing else moves; 15/06 is a run of 1
    # after a gap (not a record), 22/06 a run of 2, 29/06 3, 06/07 4; a second walk that week extends
    # no streak -- but it does make that week the biggest (996 + 995 m)
    rows2 = [row(20 + i, "walk", d, 1000 - i, dur=1000) for i, d in enumerate(
        ["2026-06-01", "2026-06-15", "2026-06-22", "2026-06-29", "2026-07-06", "2026-07-06"])]
    m2 = messages(rows2)
    assert set(m2) == {20, 22, 23, 24, 25} and m2[22]["kind"] == "streak" and "2 weeks" in m2[22]["text"], m2
    assert m2[25]["kind"] == "week" and m2[25]["also"] is None, m2[25]
    # the big week goes to the walk that CROSSED the old best, not to the one after it in the same week
    rows3 = [row(30, "walk", "2026-06-01", 5000), row(31, "walk", "2026-06-08", 3000), row(32, "walk", "2026-06-09", 4000),
             row(33, "walk", "2026-06-10", 1000)]
    m3 = messages(rows3)
    assert set(m3) == {30, 31, 32} and m3[31]["kind"] == "streak" and m3[32]["kind"] == "week" and "7.0 km" in m3[32]["text"] and m3[32]["also"] is None, m3
    # every word variant formats (a KeyError here is a template naming a field it is never given)
    for i in range(12):
        r = row(100 + i, "run", "2026-07-06", 5000, 200, 1800)
        for c in ({"kind": "pb", "label": "5 km", "metres": 5000, "value": 1700, "old": 1800, "since": "2026-07-01",
                   "barrier": None if i % 2 else 1800},
                  {"kind": "longest", "value": 5000, "old": 4000}, {"kind": "longest", "value": 5000, "old": 4999},
                  {"kind": "climb", "value": 200, "old": 100}, {"kind": "climb", "value": 200, "old": 0},
                  {"kind": "duration", "value": 1800, "old": 1500}, {"kind": "average", "value": 3.0, "old": 2.9},
                  {"kind": "week", "value": 9000, "old": 8000}, {"kind": "month", "value": 9000, "old": 8000, "key": "2026-07"},
                  {"kind": "streak", "value": 4, "old": 3}):
            title, text = _words(r, c)
            assert title and text and "{" not in text, (c, text)
    for (sport, label), (title, text) in MILESTONES.items():
        assert label in dict((lab, m) for m, lab in records.TARGETS[sport]), (sport, label)
        assert "{" not in text.format(rtime="1:00")
    for (sport, label), bars in BARRIERS.items():
        assert label in [lab for _, lab in records.TARGETS[sport]], (sport, label)
        assert bars == sorted(bars, reverse=True), (sport, label)
    for sport in scoring.SPORTS:
        assert "{" not in _first_message(row(1, sport, "2026-07-06", 5000, 100, 1800, efforts={"1 km": 300}))["text"]
    print("frontiers: selftest OK")


if __name__ == "__main__":
    selftest()      # with or without --selftest
