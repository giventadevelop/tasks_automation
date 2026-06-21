#!/usr/bin/env python3
"""Gate for scheduled Friday turnout check (read poll, cancel if < MIN_PLAYERS).

  - Fridays only (game day; poll asks for confirmation by noon)
  - Season May 12 – Oct 30
  - Run window 11:00–13:00 local (around noon)

Exit codes:
  0 = OK to run
  2 = skip (wrong day, season, time, or already checked today)
"""
from __future__ import annotations

import datetime as dt
import os
import sys

SEASON_START_MONTH = int(os.environ.get("SEASON_START_MONTH", "5"))
SEASON_START_DAY = int(os.environ.get("SEASON_START_DAY", "12"))
SEASON_END_MONTH = int(os.environ.get("SEASON_END_MONTH", "10"))
SEASON_END_DAY = int(os.environ.get("SEASON_END_DAY", "30"))
TURNOUT_WEEKDAY = int(os.environ.get("TURNOUT_WEEKDAY", "4"))  # 0=Mon … 4=Fri
TURNOUT_START_HOUR = int(os.environ.get("TURNOUT_START_HOUR", "11"))
TURNOUT_END_HOUR = int(os.environ.get("TURNOUT_END_HOUR", "13"))

_STAMP_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "tasks_automation",
)
STAMP_FILE = os.environ.get(
    "WHATSAPP_TURNOUT_STAMP",
    os.path.join(_STAMP_DIR, "whatsapp_turnout_last_run.txt"),
)


def in_volleyball_season(d: dt.date) -> bool:
    start = dt.date(d.year, SEASON_START_MONTH, SEASON_START_DAY)
    end = dt.date(d.year, SEASON_END_MONTH, SEASON_END_DAY)
    return start <= d <= end


def already_ran_today() -> bool:
    try:
        with open(STAMP_FILE, encoding="utf-8") as f:
            return f.read().strip() == dt.date.today().isoformat()
    except OSError:
        return False


def mark_ran_today() -> None:
    os.makedirs(os.path.dirname(STAMP_FILE), exist_ok=True)
    with open(STAMP_FILE, "w", encoding="utf-8") as f:
        f.write(dt.date.today().isoformat())


def should_run(now: dt.datetime | None = None) -> tuple[bool, str]:
    now = now or dt.datetime.now()
    today = now.date()
    weekday_name = today.strftime("%A")

    if now.weekday() != TURNOUT_WEEKDAY:
        return False, f"skip: today is {weekday_name}, not Friday"

    if not in_volleyball_season(today):
        return (
            False,
            f"skip: {today.isoformat()} outside season "
            f"{SEASON_START_MONTH:02d}/{SEASON_START_DAY:02d}-"
            f"{SEASON_END_MONTH:02d}/{SEASON_END_DAY:02d}",
        )

    if not (TURNOUT_START_HOUR <= now.hour < TURNOUT_END_HOUR):
        return (
            False,
            f"skip: local time {now:%H:%M} outside run window "
            f"{TURNOUT_START_HOUR:02d}:00-{TURNOUT_END_HOUR:02d}:00",
        )

    if already_ran_today():
        return False, "skip: turnout check already ran today"

    return True, (
        f"ok: Friday {today.isoformat()} in season, "
        f"window {TURNOUT_START_HOUR:02d}:00-{TURNOUT_END_HOUR:02d}:00"
    )


def main() -> int:
    ok, msg = should_run()
    print(msg, flush=True)
    if ok and len(sys.argv) > 1 and sys.argv[1] == "--mark":
        mark_ran_today()
        print(f"marked ran: {STAMP_FILE}", flush=True)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
