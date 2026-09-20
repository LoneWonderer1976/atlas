"""sports.py -- Garmin's activity type -> Argo's five sports.

Garmin labels an activity with a typeKey such as `trail_running` or `open_water_swimming`;
Argo pays by one of five words. The match is on the KEY'S WORDS, so a type Garmin adds next
year lands in the right sport if it says what it is, and anything else reads as "other" --
listed on the page, paid nothing, and printed on the statement so Ben can see what the watch
is calling things.
"""

_RULES = (
    # (sport, words that place a typeKey in it) -- first match wins, most specific first
    ("kayak", ("kayak", "paddl", "canoe", "sup", "stand_up", "rowing")),
    ("swim",  ("swim",)),
    ("run",   ("run", "treadmill", "track")),
    ("cycle", ("cycl", "bik", "ride", "bmx", "velo")),
    ("walk",  ("walk", "hik", "trek")),
)


def sport_for(type_key: str | None) -> str:
    key = (type_key or "").lower()
    for sport, words in _RULES:
        if any(w in key for w in words):
            return sport
    return "other"


def selftest() -> None:
    cases = {
        "running": "run", "trail_running": "run", "treadmill_running": "run", "track_running": "run",
        "cycling": "cycle", "road_biking": "cycle", "mountain_biking": "cycle", "indoor_cycling": "cycle",
        "gravel_cycling": "cycle", "virtual_ride": "cycle", "e_bike_fitness": "cycle",
        "walking": "walk", "hiking": "walk", "casual_walking": "walk",
        "lap_swimming": "swim", "open_water_swimming": "swim", "swimming": "swim",
        "kayaking": "kayak", "sea_kayaking": "kayak", "paddling": "kayak", "stand_up_paddleboarding": "kayak",
        "football": "other", "strength_training": "other", None: "other", "": "other",
    }
    for key, want in cases.items():
        got = sport_for(key)
        assert got == want, (key, got, want)
    print("sports: selftest OK")


if __name__ == "__main__":
    selftest()      # with or without --selftest
