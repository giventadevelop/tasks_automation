#!/usr/bin/env python3

"""Gate for scheduled WhatsApp poll runs.



  - Thursdays only (day before Friday volleyball)

  - Season May 12 – Oct 30

  - Run window 08:00–23:00 local (hourly retries until 11 PM if not yet successful)



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

SCHEDULE_WEEKDAY = int(os.environ.get("SCHEDULE_WEEKDAY", "3"))  # 0=Mon … 3=Thu

SCHEDULE_START_HOUR = int(os.environ.get("SCHEDULE_START_HOUR", "8"))

SCHEDULE_END_HOUR = int(os.environ.get("SCHEDULE_END_HOUR", "23"))  # retries until 11 PM



_STAMP_DIR = os.path.join(

    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),

    "tasks_automation",

)

STAMP_FILE = os.environ.get(

    "WHATSAPP_POLL_STAMP",

    os.path.join(_STAMP_DIR, "whatsapp_poll_last_run.txt"),

)





def in_volleyball_season(d: dt.date) -> bool:

    start = dt.date(d.year, SEASON_START_MONTH, SEASON_START_DAY)

    end = dt.date(d.year, SEASON_END_MONTH, SEASON_END_DAY)

    return start <= d <= end





def should_run(now: dt.datetime | None = None) -> tuple[bool, str]:

    now = now or dt.datetime.now()

    today = now.date()

    weekday_name = today.strftime("%A")



    if now.weekday() != SCHEDULE_WEEKDAY:

        return False, f"skip: today is {weekday_name}, not Thursday"



    if not in_volleyball_season(today):

        return (

            False,

            f"skip: {today.isoformat()} outside season "

            f"{SEASON_START_MONTH:02d}/{SEASON_START_DAY:02d}-"

            f"{SEASON_END_MONTH:02d}/{SEASON_END_DAY:02d}",

        )



    if not (SCHEDULE_START_HOUR <= now.hour <= SCHEDULE_END_HOUR):

        return (

            False,

            f"skip: local time {now:%H:%M} outside run window "

            f"{SCHEDULE_START_HOUR:02d}:00-{SCHEDULE_END_HOUR:02d}:00",

        )



    if succeeded_today("poll"):

        return False, "skip: poll already succeeded today"



    rec = record_for_today("poll")

    if rec and rec.get("status") == "failed":

        return True, (

            f"ok: Thursday {today.isoformat()} retry "

            f"(attempt {rec.get('attempts', 0) + 1}, previous failure)"

        )



    return True, (

        f"ok: Thursday {today.isoformat()} in season, "

        f"window {SCHEDULE_START_HOUR:02d}:00-{SCHEDULE_END_HOUR:02d}:00"

    )





def main() -> int:

    ok, msg = should_run()

    print(msg, flush=True)

    if len(sys.argv) > 1:

        arg = sys.argv[1]

        if arg in ("--mark", "--mark-success"):
            detail = sys.argv[2] if len(sys.argv) > 2 else "poll sent"
            mark_success("poll", detail=detail)
            print(f"marked success: {STAMP_FILE}", flush=True)
        elif arg == "--mark-failed":

            detail = sys.argv[2] if len(sys.argv) > 2 else "scheduled run failed"

            mark_failed("poll", detail=detail)

            print(status_summary("poll"), flush=True)

        elif arg == "--status":

            print(status_summary("poll"), flush=True)

            rec = record_for_today("poll")

            if rec:

                print(rec, flush=True)

    return 0 if ok else 2





if __name__ == "__main__":

    raise SystemExit(main())

