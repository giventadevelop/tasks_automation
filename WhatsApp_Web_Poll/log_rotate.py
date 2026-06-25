#!/usr/bin/env python3
"""Rotate WhatsApp_Web_Poll/logs — delete log files older than KEEP_DAYS."""
from __future__ import annotations

import datetime as dt
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
KEEP_DAYS = int(os.environ.get("LOG_KEEP_DAYS", "14"))
LOG_PATTERN = re.compile(
    r"^(whatsapp_poll|whatsapp_turnout)_(\d{8})\.log$", re.IGNORECASE
)


def main() -> int:
    if not os.path.isdir(LOG_DIR):
        print(f"no log dir: {LOG_DIR}", flush=True)
        return 0

    cutoff = dt.date.today() - dt.timedelta(days=KEEP_DAYS)
    removed = 0
    kept = 0
    for name in os.listdir(LOG_DIR):
        m = LOG_PATTERN.match(name)
        if not m:
            continue
        try:
            log_date = dt.datetime.strptime(m.group(2), "%Y%m%d").date()
        except ValueError:
            continue
        path = os.path.join(LOG_DIR, name)
        if log_date < cutoff:
            try:
                os.remove(path)
                print(f"removed old log: {name}", flush=True)
                removed += 1
            except OSError as exc:
                print(f"could not remove {name}: {exc}", flush=True)
        else:
            kept += 1

    print(f"log rotation: kept={kept} removed={removed} (keep {KEEP_DAYS} days)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
