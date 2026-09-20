# Atlas — design log

The reasoning, in the order the decisions were made. `README.md` says how to run it; this says
why it is the shape it is.

## What it is (20/09/2026)

The third app in the family — Nostos Datum is Ben's, Argo is Thomas's, Atlas is Joe's. Ben:
*"same method but I want his app to be heavy on stats, tables and charts, rank his activities,
chart his progress etc."* Then: *"Atlas, he's called Joe, same 5 sports, pure stats no reward
layer, he got his Garmin this July with his own account."*

| | |
|---|---|
| Name | Atlas — the one who carries the numbers |
| Person | Joe, 19; his own Garmin Connect account; history from July 2026 (`HISTORY_START` = 1 June, harmlessly early) |
| Sports | run, walk, cycle, swim, kayak — Argo's `sports.py`, unchanged |
| Reward layer | none. The Atlas *score* exists only to rank activities |
| Hosting | GitHub Actions + Pages, as Argo; the repo public for the same reason (Pages on the free plan) |
| Folder | `C:\Atlas`, its own repo; the modules that carry over from Argo were copied, not imported |

## What carries over from Argo, and what does not

Same skeleton: `sync.py` (Garmin → `data/`), a derive step that writes `docs/data.json`, a static
page on Pages, an hourly Action, `setup.py` + `login.py` for the two logins. Same rules: the data
folder is the database, nothing derived is stored, the watch's local clock names the week,
corrections live in `overrides.json` and are applied before anything is computed.

Gone: money, the ledger, the statement, the reply parser, the Easter eggs. In their place, the
things a stats page needs and Argo did not:

- **The timeline, not just the summary.** A best effort is the fastest stretch of a target
  distance *inside* an activity — the quickest 5 km in a 12 km run — and no summary carries it.
  So the sync downloads each activity's **TCX** and keeps its trackpoints as four parallel
  arrays (`data/streams/<id>.json`: seconds, the device's own cumulative metres, altitude, heart
  rate). The device's `DistanceMeters` is used rather than a haversine over positions because it
  is what the watch itself measured (wheel, foot pod, GPS-smoothed), it exists for pool swims
  that have no positions, and it is already monotone up to GPS hiccups, which `parse_tcx` clamps.
- **`records.fastest()`** is a two-pointer sweep over cumulative distance with `bisect`, O(n),
  interpolating the finish to the exact target so a 5,003 m window is not a 5 km. Ladders per
  sport are `TARGETS`; a "fastest average" record needs `AVG_FLOOR_M` so a 300 m dash is not the
  fastest run. Times are elapsed, not moving: a stop at a road crossing costs a record, as it
  would in a race.
- **Rank** is by the Atlas score — Nostos Datum's activity score (distance by sport plus climb),
  copied as Argo copied it. It is a ranking axis, not a judgement: everything else on the page is
  measured directly. Struck and unscored activities are unranked, not last.
- **Progression** — for each (sport, target) every attempt with the running best beside it, so
  the records chart draws attempts as dots and the record as a stepped line, and a dot in the
  accent colour is the day it was broken.
- **The fitness chart.** Pace (min/mile, axis reversed so up is faster) and average heart rate on
  one chart per run over 1 km, sized by distance. The signal is the gap: heart rate falling at
  the same pace, or pace falling at the same heart rate. Cycling gets the same in km/h.
- **Streaks** count weeks with at least one activity, and the current streak tolerates this week
  being empty so a Monday morning does not read as a broken run.

## The page

Six tabs in a fixed bottom bar (Overview, Records, Rank, Progress, Log, Map), each rendered on
first open and every chart destroyed and rebuilt on a reload, so a `visibilitychange` refresh
never stacks a chart on a used canvas (Argo's first bug). The Log is a real table — sort by any
column, filter by sport, horizontal scroll on a phone — because a stats page for a nineteen-year-
old should not be all cards. The Map draws every track at once, coloured by sport, fitted as they
load; at Joe's volume that is tens of small files, not thousands. Tapping anything opens the
activity sheet: the numbers, its map, its best efforts with **PB** where it holds the record.

## Not built, deliberately

- **Heart-rate zones and training load.** They need Joe's max HR / thresholds (his to give) and
  a model nobody has chosen; the pace/HR chart says most of it without inventing a number.
- **Age-grading, VO2max curves.** The summary carries Garmin's VO2max estimate; it is stored, not
  yet charted. Chart it when there are enough months to see a slope.
- **Segments / route matching.** Real, valuable, and a build on its own (Nostos Datum's
  route-identity work is the size of it). The records board covers the everyday question.
