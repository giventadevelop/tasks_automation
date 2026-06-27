#!/usr/bin/env python3
"""Persist success/failure status for scheduled WhatsApp poll and turnout runs."""
from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any

_STATUS_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "tasks_automation",
)

KIND_FILES = {
    "poll": os.environ.get(
        "WHATSAPP_POLL_STATUS",
        os.path.join(_STATUS_DIR, "whatsapp_poll_status.json"),
    ),
    "turnout": os.environ.get(
        "WHATSAPP_TURNOUT_STATUS",
        os.path.join(_STATUS_DIR, "whatsapp_turnout_status.json"),
    ),
}

# Legacy stamp files (kept in sync on success for older tooling)
LEGACY_STAMPS = {
    "poll": os.path.join(_STATUS_DIR, "whatsapp_poll_last_run.txt"),
    "turnout": os.path.join(_STATUS_DIR, "whatsapp_turnout_last_run.txt"),
}


def _path(kind: str) -> str:
    if kind not in KIND_FILES:
        raise ValueError(f"unknown kind: {kind}")
    return KIND_FILES[kind]


def _read(kind: str) -> dict[str, Any]:
    path = _path(kind)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write(kind: str, data: dict[str, Any]) -> None:
    os.makedirs(_STATUS_DIR, exist_ok=True)
    with open(_path(kind), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def today_iso() -> str:
    return dt.date.today().isoformat()


def record_for_today(kind: str) -> dict[str, Any] | None:
    data = _read(kind)
    if data.get("date") == today_iso():
        return data
    return None


def succeeded_today(kind: str) -> bool:
    rec = record_for_today(kind)
    return bool(rec and rec.get("status") == "success")


def message_sent_today(kind: str) -> bool:
    """True only when a WhatsApp status message was actually sent today."""
    rec = record_for_today(kind)
    if not rec or rec.get("status") != "success":
        return False
    if rec.get("message_sent") is True:
        return True
    if rec.get("message_sent") is False:
        return False
    detail = str(rec.get("detail", ""))
    return detail in ("go_msg", "weather_rain", "weather_temp", "low_turnout")


def failed_today(kind: str) -> bool:
    rec = record_for_today(kind)
    return bool(rec and rec.get("status") == "failed")


def attempts_today(kind: str) -> int:
    rec = record_for_today(kind)
    return int(rec.get("attempts", 0)) if rec else 0


def mark_success(kind: str, detail: str = "", message_sent: bool | None = None) -> None:
    rec = record_for_today(kind) or {"date": today_iso(), "attempts": 0}
    rec.update(
        {
            "date": today_iso(),
            "status": "success",
            "last_attempt": dt.datetime.now().isoformat(timespec="seconds"),
            "detail": detail,
        }
    )
    if message_sent is not None:
        rec["message_sent"] = message_sent
    _write(kind, rec)
    legacy = LEGACY_STAMPS.get(kind)
    if legacy:
        os.makedirs(os.path.dirname(legacy), exist_ok=True)
        with open(legacy, "w", encoding="utf-8") as f:
            f.write(today_iso())


def mark_failed(kind: str, detail: str = "", exit_code: int | None = None) -> None:
    rec = record_for_today(kind) or {"date": today_iso(), "attempts": 0}
    attempts = int(rec.get("attempts", 0)) + 1
    rec.update(
        {
            "date": today_iso(),
            "status": "failed",
            "attempts": attempts,
            "last_attempt": dt.datetime.now().isoformat(timespec="seconds"),
            "detail": detail,
        }
    )
    if exit_code is not None:
        rec["exit_code"] = exit_code
    _write(kind, rec)


def mark_attempt(kind: str) -> None:
    rec = record_for_today(kind) or {"date": today_iso(), "status": "pending", "attempts": 0}
    rec["attempts"] = int(rec.get("attempts", 0)) + 1
    rec["last_attempt"] = dt.datetime.now().isoformat(timespec="seconds")
    if rec.get("status") not in ("success", "failed"):
        rec["status"] = "pending"
    _write(kind, rec)


def status_summary(kind: str) -> str:
    rec = record_for_today(kind)
    if not rec:
        return f"{kind}: no run today"
    return (
        f"{kind}: {rec.get('status', '?')} "
        f"attempts={rec.get('attempts', 0)} "
        f"detail={rec.get('detail', '')!r}"
    )
