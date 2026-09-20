"""fix.py -- the two corrections a person makes: strike an activity, or relabel its sport.

    python -m atlas.fix --strike 12345678 --reason "watch left running" --apply
    python -m atlas.fix --unstrike 12345678 --apply
    python -m atlas.fix --sport 12345678 kayak --apply

Dry-run by default; --apply writes data/overrides.json. Everything derived re-derives on the next
`python -m atlas.stats` (or the hourly Action).
"""
import argparse

from . import scoring, store


def strike(activity_id: str, reason: str | None, apply: bool) -> None:
    if not (store.ACTS / f"{activity_id}.json").exists():
        raise SystemExit(f"no activity {activity_id} in data/activities")
    ov = store.overrides()
    print(f"{'STRIKE' if apply else 'would strike'} {activity_id}: {reason or 'struck'}")
    if apply:
        ov["exclude"][str(activity_id)] = reason or "struck"
        store.write_overrides(ov)


def unstrike(activity_id: str, apply: bool) -> None:
    ov = store.overrides()
    if str(activity_id) not in ov["exclude"]:
        raise SystemExit(f"{activity_id} is not struck")
    print(f"{'UNSTRIKE' if apply else 'would unstrike'} {activity_id} (was: {ov['exclude'][str(activity_id)]})")
    if apply:
        del ov["exclude"][str(activity_id)]
        store.write_overrides(ov)


def relabel(activity_id: str, sport: str, apply: bool) -> None:
    if sport not in scoring.SPORTS:
        raise SystemExit(f"'{sport}' is not one of {', '.join(scoring.SPORTS)}")
    if not (store.ACTS / f"{activity_id}.json").exists():
        raise SystemExit(f"no activity {activity_id} in data/activities")
    ov = store.overrides()
    print(f"{'RELABEL' if apply else 'would relabel'} {activity_id} as {sport}")
    if apply:
        ov["sport"][str(activity_id)] = sport
        store.write_overrides(ov)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strike", metavar="ID")
    ap.add_argument("--reason")
    ap.add_argument("--unstrike", metavar="ID")
    ap.add_argument("--sport", nargs=2, metavar=("ID", "SPORT"))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.sport:
        relabel(a.sport[0], a.sport[1], a.apply)
    elif a.strike:
        strike(a.strike, a.reason, a.apply)
    elif a.unstrike:
        unstrike(a.unstrike, a.apply)
    else:
        ap.print_help()
        return
    if not a.apply:
        print("(dry run -- add --apply)")


if __name__ == "__main__":
    main()
