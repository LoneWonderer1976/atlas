# 🗺️ Atlas

Joe's training, measured. His Garmin records the activity; Atlas turns every one into numbers —
best efforts (the fastest 5 km *inside* a run, not its average), a records board, rankings,
weekly and monthly volume, pace-against-heart-rate fitness charts, streaks, a sortable log and a
map of everywhere he has been. No rewards, no money: stats.

Nothing runs anywhere but GitHub: an Action syncs from Garmin every hour, recomputes everything,
and publishes the page to GitHub Pages. The data is JSON in this repo.

## Setting it up

`gh` is already logged in from Argo, and `python setup.py` has been run (the repo, Pages and the
page address exist). The one thing left needs Joe's Garmin password typed by a person:

```bash
python -m atlas.login
```

It asks for the email and password of the account his watch syncs to (and an MFA code if there
is one), stores the tokens as the `GARMINTOKENS` secret, starts the first sync on GitHub and
fetches his activities here too. The tokens last about a year; when the *sync* Action starts
failing to log in, run it again.

Then `https://<you>.github.io/atlas/` on his phone → *Add to Home Screen*.

## What is on the page

| tab | what |
|---|---|
| **Overview** | all-time distance / time / climb / streak; this week against last; the last 12 weeks by sport; totals per sport; the latest activities |
| **Records** | per sport: fastest 400 m · 1 km · 1 mile · 5 km · 10 km · half · marathon (runs), 5 km … 100 km (rides), and so on; longest, most climb, longest time, fastest average over a floor distance; biggest week and month. Tap a record for its **progression** — every attempt as a dot, the record as it stood as a line |
| **Rank** | every activity by the Atlas score (distance by sport plus climb — `atlas/scoring.py`), overall or within a sport |
| **Progress** | weekly and monthly distance stacked by sport, monthly climb, **running pace and heart rate over time** (fitness is HR coming down at the same pace), the same for cycling speed, cumulative distance this year, consistency |
| **Log** | every activity in a table — tap a heading to sort, a chip to filter, a row for the detail |
| **Map** | every track, coloured by sport; tap a line for the activity |

Tapping any activity opens its sheet: the numbers, its map, and its best efforts with **PB**
marked where it holds the record.

## Corrections

The watch is occasionally wrong. Two corrections, both in `data/overrides.json` and both applied
before anything is computed:

```bash
python -m atlas.fix --strike 12345678 --reason "watch left running" --apply
python -m atlas.fix --sport 12345678 kayak --apply         # the watch said "other"
```

## On the PC

```bash
python check.py                 # every selftest + pyflakes
python -m atlas.sync --dry-run  # what Garmin has that we do not
python -m atlas.stats --print   # the headline numbers, the records and the top 10 (rebuilds docs/data.json)
python -m atlas.demo            # a made-up data.json to look at the page before the first sync
```

Scripts that write are dry-run by default and take `--apply`. The design log is
[`ATLAS_BRIEF.md`](ATLAS_BRIEF.md).
