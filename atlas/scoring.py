"""scoring.py -- the Atlas score: one number per activity so activities can be RANKED.

It is Nostos Datum's activity score, copied as Argo's was (Ben, 20/09/2026: "same method"):
distance per mile by sport, swimming per 100 m, plus ascent. It is not money here -- it is the
ranking axis, and everything else on the page (pace, records, volume) is measured directly.
Change a number and every rank re-derives on the next run.
"""
SPORTS = ("run", "walk", "cycle", "swim", "kayak")
DISTANCE_PER_MILE = {"cycle": 1.0, "walk": 2.0, "run": 4.0, "kayak": 4.0}
SWIM_PTS_PER_100M = 1.0
ASCENT_PTS_PER_M = {"cycle": 1.0 / 100, "walk": 1.0 / 50, "run": 1.0 / 25}
MILES_PER_METRE = 1.0 / 1609.344
MIN_DISTANCE_M = 100.0

# plausibility flags, as in Argo: shown, never enforced
MAX_SPEED_MPS = {"run": 7.0, "walk": 3.0, "cycle": 18.0, "swim": 2.5, "kayak": 5.0}


def score(sport: str, distance_m: float | None, ascent_m: float | None) -> float:
    if sport not in SPORTS or not distance_m or distance_m < MIN_DISTANCE_M:
        return 0.0
    pts = distance_m / 100.0 * SWIM_PTS_PER_100M if sport == "swim" else distance_m * MILES_PER_METRE * DISTANCE_PER_MILE[sport]
    if ascent_m and sport in ASCENT_PTS_PER_M:
        pts += ascent_m * ASCENT_PTS_PER_M[sport]
    return pts


def selftest() -> None:
    assert abs(score("run", 1609.344, 25) - 5.0) < 1e-9
    assert score("swim", 1000, 0) == 10.0 and score("kayak", 1609.344, 100) == 4.0
    assert score("other", 5000, 0) == 0.0 and score("run", 50, 0) == 0.0
    print("scoring: selftest OK")


if __name__ == "__main__":
    selftest()      # with or without --selftest
