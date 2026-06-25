#!/usr/bin/env python3
"""Gate for scheduled Friday turnout check (read poll, cancel if Yes < MIN_PLAYERS).

  - Fridays only (game day)
  - Season May 12 – Oct 30
  - Run at 15:00 (3 PM) and 16:00 (4 PM) — second slot is retry if first failed

Exit codes:
  0 = OK to run
  2 = skip (wrong day, season, time, or already succeeded today)
"""
from __future__ import annotations

import datetime as dt
import os
import sys

from run_status import mark_failed, mark_success, record_for_today, succeeded_today, status_summary

SEASON_START_MONTH = int(os.environ.get("SEASON_START_MONTH", "5"))
SEASON_START_DAY = int(os.environ.get("SEASON_START_DAY", "12"))
SEASON_END_MONTH = int(os.environ.get("SEASON_END_MONTH", "10"))
SEASON_END_DAY = int(os.environ.get("SEASON_END_DAY", "30"))
TURNOUT_WEEKDAY = int(os.environ.get("TURNOUT_WEEKDAY", "4"))  # 0=Mon … 4=Fri
# Comma-separated hours: 3 PM primary, 4 PM retry
TURNOUT_RUN_HOURS = tuple(
    int(h.strip())
    for h in os.environ.get("TURNOUT_RUN_HOURS", "15,16").split(",")
    if h.strip()
)

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

    if now.hour not in TURNOUT_RUN_HOURS:
        slots = ", ".join(f"{h:02d}:00" for h in TURNOUT_RUN_HOURS)
        return False, f"skip: local time {now:%H:%M} not in turnout slots ({slots})"

    if succeeded_today("turnout"):
        return False, "skip: turnout check already succeeded today"

    rec = record_for_today("turnout")
    slot = f"{now.hour:02d}:00"
    if rec and rec.get("status") == "failed":
        return True, (
            f"ok: Friday {today.isoformat()} turnout retry at {slot} "
            f"(attempt {rec.get('attempts', 0) + 1})"
        )

    return True, f"ok: Friday {today.isoformat()} turnout check at {slot}"


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
