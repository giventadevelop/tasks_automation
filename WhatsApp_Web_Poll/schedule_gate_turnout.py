#!/usr/bin/env python3
"""Gate for scheduled Friday turnout check (read poll, send Friday status message).

  - Fridays only (game day)
  - Season May 12 – Oct 30
  - Run window 15:00–17:00 local, every 20 minutes (Task Scheduler repetition)
  - Stops retrying after any message was sent successfully today

Exit codes:
  0 = OK to run
  2 = skip (wrong day, season, time, or already succeeded today)
"""
from __future__ import annotations

import datetime as dt
import os
import sys

from run_status import mark_failed, mark_success, message_sent_today, record_for_today, status_summary

SEASON_START_MONTH = int(os.environ.get("SEASON_START_MONTH", "5"))
SEASON_START_DAY = int(os.environ.get("SEASON_START_DAY", "12"))
SEASON_END_MONTH = int(os.environ.get("SEASON_END_MONTH", "10"))
SEASON_END_DAY = int(os.environ.get("SEASON_END_DAY", "30"))
TURNOUT_WEEKDAY = int(os.environ.get("TURNOUT_WEEKDAY", "4"))  # 0=Mon … 4=Fri
TURNOUT_WINDOW_START_HOUR = int(os.environ.get("TURNOUT_WINDOW_START_HOUR", "15"))
TURNOUT_WINDOW_START_MINUTE = int(os.environ.get("TURNOUT_WINDOW_START_MINUTE", "0"))
TURNOUT_WINDOW_END_HOUR = int(os.environ.get("TURNOUT_WINDOW_END_HOUR", "17"))
TURNOUT_WINDOW_END_MINUTE = int(os.environ.get("TURNOUT_WINDOW_END_MINUTE", "0"))
TURNOUT_INTERVAL_MINUTES = int(os.environ.get("TURNOUT_INTERVAL_MINUTES", "20"))

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


def _minutes_of_day(hour: int, minute: int) -> int:
    return hour * 60 + minute


def in_turnout_window(now: dt.datetime) -> bool:
    now_m = _minutes_of_day(now.hour, now.minute)
    start_m = _minutes_of_day(TURNOUT_WINDOW_START_HOUR, TURNOUT_WINDOW_START_MINUTE)
    end_m = _minutes_of_day(TURNOUT_WINDOW_END_HOUR, TURNOUT_WINDOW_END_MINUTE)
    return start_m <= now_m <= end_m


def should_run(now: dt.datetime | None = None) -> tuple[bool, str]:
    now = now or dt.datetime.now()
    today = now.date()
    weekday_name = today.strftime("%A")
    slot = now.strftime("%H:%M")

    if now.weekday() != TURNOUT_WEEKDAY:
        return False, f"skip: today is {weekday_name}, not Friday"

    if not in_volleyball_season(today):
        return (
            False,
            f"skip: {today.isoformat()} outside season "
            f"{SEASON_START_MONTH:02d}/{SEASON_START_DAY:02d}-"
            f"{SEASON_END_MONTH:02d}/{SEASON_END_DAY:02d}",
        )

    if not in_turnout_window(now):
        return (
            False,
            f"skip: local time {slot} outside turnout window "
            f"{TURNOUT_WINDOW_START_HOUR:02d}:{TURNOUT_WINDOW_START_MINUTE:02d}-"
            f"{TURNOUT_WINDOW_END_HOUR:02d}:{TURNOUT_WINDOW_END_MINUTE:02d} "
            f"(every {TURNOUT_INTERVAL_MINUTES} min)",
        )

    if message_sent_today("turnout"):
        return False, "skip: turnout message already sent successfully today"

    rec = record_for_today("turnout")
    if rec and rec.get("status") == "failed":
        return True, (
            f"ok: Friday {today.isoformat()} turnout retry at {slot} "
            f"(attempt {rec.get('attempts', 0) + 1}, next try every {TURNOUT_INTERVAL_MINUTES} min until "
            f"{TURNOUT_WINDOW_END_HOUR:02d}:{TURNOUT_WINDOW_END_MINUTE:02d})"
        )

    return True, (
        f"ok: Friday {today.isoformat()} turnout check at {slot} "
        f"(window until {TURNOUT_WINDOW_END_HOUR:02d}:{TURNOUT_WINDOW_END_MINUTE:02d}, "
        f"every {TURNOUT_INTERVAL_MINUTES} min)"
    )


def main() -> int:
    ok, msg = should_run()
    print(msg, flush=True)
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ("--mark", "--mark-success"):
            detail = sys.argv[2] if len(sys.argv) > 2 else "turnout check completed"
            mark_success("turnout", detail=detail)
            print(f"marked success: {STAMP_FILE}", flush=True)
        elif arg == "--mark-failed":
            detail = sys.argv[2] if len(sys.argv) > 2 else "turnout check failed"
            mark_failed("turnout", detail=detail)
            print(status_summary("turnout"), flush=True)
        elif arg == "--status":
            print(status_summary("turnout"), flush=True)
            rec = record_for_today("turnout")
            if rec:
                print(rec, flush=True)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
