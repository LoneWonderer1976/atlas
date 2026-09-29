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

## The PB ladders, in miles and kilometres (20/09/2026, late)

Ben: *"for Joe can we add more run distances and also cycles both miles and kilometres — for
PBs."* `records.TARGETS` now runs 400 m → marathon in sixteen steps for running (both units:
1 km and 1 mile, 2 km and 2 miles, 5 km and 5 miles, 10 km and 10 miles, 15 km, 20 km, half,
30 km), fifteen for cycling (1 km → 100 miles, likewise both), and the walk, swim and kayak
ladders grew a rung or two. The ladders are shipped in `data.json` as `targets`, so the page
reads distances from the same table the records are computed from rather than carrying its
own copy — the activity sheet lists an activity's efforts in ladder order with the pace
against each. A record exists only once an activity has covered the distance, so a rung the
watch has never seen is simply absent, not a blank.

## The page

Six tabs in a fixed bottom bar (Overview, Records, Rank, Progress, Log, Map), each rendered on
first open and every chart destroyed and rebuilt on a reload, so a `visibilitychange` refresh
never stacks a chart on a used canvas (Argo's first bug). The Log is a real table — sort by any
column, filter by sport, horizontal scroll on a phone — because a stats page for a nineteen-year-
old should not be all cards. The Map draws every track at once, coloured by sport, fitted as they
load; at Joe's volume that is tens of small files, not thousands. Tapping anything opens the
activity sheet: the numbers, its map, its best efforts with **PB** where it holds the record.

## The congratulations: one message per frontier moved (29/09/2026)

Ben: *"add some congratulatory messages to Joe that are revealed when he hits a new record,
longest walk, fastest 5k etc, only 1 message per activity, the most relevant whenever a frontier
is moved."*

`atlas/frontiers.py` replays the activities **oldest first**, carrying every frontier the records
board shows (the fastest time at each rung, longest, most climb, longest time, fastest average,
biggest week and month) plus the longest streak. Whatever an activity moved *at the time it
happened* is a candidate. The most relevant one becomes its message, and the rest go on one line
under it (*Also moved: fastest 400 m, 800 m … ; longest run*). That keeps it to one message
without hiding the other records. It is derived on every run like everything else: strike an old
activity and the messages after it change on the next build, because the struck one no longer
sets the bar.

**Most relevant** is a fixed order (`ORDER`), because "the biggest improvement" would need
exchange rates between seconds, metres and weeks, and there is no honest way to set them:

1. **The first activity of a sport.** Its whole board is new, so nothing else is said.
2. **A milestone**, the first time over a named distance (`MILESTONES`: the first 5 km run, half
   marathon, 100 km ride, 10-mile walk, mile swim …). Each has its own message. Covering a new rung
   always means a new longest as well, and the named distance is the better sentence.
3. **Then the sport decides.** Running and swimming are about speed, so a PB comes before the
   longest. Walking, cycling and paddling are about distance, so the longest comes first, then the
   most climb, then a PB. That is how the brief put it: *longest walk*, *fastest 5k*.
   Among several PBs in one run, a **barrier** wins (`BARRIERS`: under 30 minutes for 5 km, under
   2 hours for the half; the moment a runner remembers), then the **longest rung**. That is the one
   he would quote, and the one least at the mercy of a GPS wobble.
4. Fastest average, most climb, longest time, biggest week, biggest month, longest streak.

A week, month or streak record goes to the activity that **crossed** the old best, not to every
later one in the same week. The first week, month and streak are not records, because there was
nothing to beat. On Joe's history as it stood (10 activities), 9 carry a message. The 0.7 km walk
on 1 August moved nothing, so it has none.

The words are content, written in the module: several variants per kind, picked by activity id so
an activity always reads the same. No message repeats its own title. **Revealed** means the pop-up:
on opening the page, an unseen message appears once (🏆, the title, the words, *See the run* /
*Brilliant!*). What has been seen is kept per phone in `localStorage`. A backlog (a new phone, a
month away) shows only the newest three, and the rest are marked seen and sit in Records. After
that each message lives on its activity's sheet, in **Records → Frontiers moved** (newest first,
following the sport chips), and as a 🏆 on the activity's card and Log row.

## Not built, deliberately

- **Heart-rate zones and training load.** They need Joe's max HR / thresholds (his to give) and
  a model nobody has chosen; the pace/HR chart says most of it without inventing a number.
- **Age-grading, VO2max curves.** The summary carries Garmin's VO2max estimate; it is stored, not
  yet charted. Chart it when there are enough months to see a slope.
- **Segments / route matching.** Real, valuable, and a build on its own (Nostos Datum's
  route-identity work is the size of it). The records board covers the everyday question.
