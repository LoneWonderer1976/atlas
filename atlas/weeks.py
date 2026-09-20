"""weeks.py -- the pocket-money week: Monday to Sunday, on UK time.

A week is named by its Monday (ISO date). Garmin gives an activity's start as LOCAL time
(`startTimeLocal`, the watch's own zone), which is what a person means by "Tuesday's run",
so the week is taken from that string and never from the UTC instant.
"""
import datetime as dt
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")


def week_of(day: dt.date) -> dt.date:
    """The Monday that starts the week holding `day`."""
    return day - dt.timedelta(days=day.weekday())


def week_for(start_local: str) -> dt.date:
    """The week of a Garmin `startTimeLocal` ('2026-09-22 16:05:00')."""
    return week_of(dt.date.fromisoformat(start_local[:10]))


def today_uk() -> dt.date:
    return dt.datetime.now(UK).date()


def this_week() -> dt.date:
    return week_of(today_uk())


def last_week() -> dt.date:
    """The most recently COMPLETED week -- what the Sunday statement is about."""
    return this_week() - dt.timedelta(days=7)


def week_label(monday: dt.date) -> str:
    sunday = monday + dt.timedelta(days=6)
    if monday.month == sunday.month:
        return f"{monday.day}–{sunday.day} {sunday:%b %Y}"
    return f"{monday.day} {monday:%b} – {sunday.day} {sunday:%b %Y}"


def selftest() -> None:
    assert week_of(dt.date(2026, 9, 20)) == dt.date(2026, 9, 14)        # a Sunday -> its Monday
    assert week_of(dt.date(2026, 9, 21)) == dt.date(2026, 9, 21)        # a Monday -> itself
    assert week_for("2026-09-27 23:59:00") == dt.date(2026, 9, 21)
    assert week_for("2026-09-28 00:00:01") == dt.date(2026, 9, 28)
    assert week_label(dt.date(2026, 9, 21)) == "21–27 Sep 2026"
    assert week_label(dt.date(2026, 9, 28)) == "28 Sep – 4 Oct 2026"
    assert this_week().weekday() == 0 and last_week() == this_week() - dt.timedelta(days=7)
    print("weeks: selftest OK")


if __name__ == "__main__":
    selftest()      # with or without --selftest
