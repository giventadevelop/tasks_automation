#!/usr/bin/env python3
"""Build logs/index.html — local viewer for WhatsApp poll / turnout run logs."""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
OUT_FILE = os.path.join(LOG_DIR, "index.html")
LOG_PATTERN = re.compile(
    r"^(whatsapp_poll|whatsapp_turnout)_(\d{8})(?:_(\d{2}))?\.log$", re.IGNORECASE
)
RUN_SPLIT = re.compile(r"={10,}")
RUN_STARTED = re.compile(
    r"\[([^\]]+)\]\s*scheduled run started", re.IGNORECASE
)
POLL_TASK = "WhatsApp Volleyball Poll (Thursday)"
STAMP_POLL = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "tasks_automation",
    "whatsapp_poll_last_run.txt",
)
STAMP_TURNOUT = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "tasks_automation",
    "whatsapp_turnout_last_run.txt",
)
STATUS_POLL = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "tasks_automation",
    "whatsapp_poll_status.json",
)
STATUS_TURNOUT = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "tasks_automation",
    "whatsapp_turnout_status.json",
)


def read_stamp(path: str) -> str:
    try:
        return open(path, encoding="utf-8").read().strip()
    except OSError:
        return "(none)"


def read_status_record(path: str) -> dict | None:
    try:
        data = json.load(open(path, encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def classify_body(body: str) -> str:
    lower = body.lower()
    if "done exit=0" in lower or "marked success" in lower or "poll sent" in lower:
        return "success"
    if "failed" in lower or "fail:" in lower or "timeout" in lower:
        if "will retry next hour" in lower:
            return "failed"
        if "fail:" in lower or " failed" in lower:
            return "failed"
    if "schedule gate: skip" in lower or "skip:" in lower:
        return "skipped"
    if "schedule gate: proceed" in lower or "scheduled run started" in lower:
        if "[wapoll]" not in lower and "whatsapp_poll.py exit=" not in lower:
            return "incomplete"
    return "unknown"


def parse_run_blocks(body: str) -> list[dict]:
    """Split a log file into individual scheduled run attempts."""
    blocks: list[dict] = []
    if not body.strip():
        return blocks
    parts = RUN_SPLIT.split(body)
    for part in parts:
        part = part.strip()
        if not part or "scheduled run started" not in part.lower():
            continue
        m = RUN_STARTED.search(part)
        started = m.group(1).strip() if m else ""
        status = classify_body(part)
        blocks.append({"started": started, "status": status, "body": part})
    if not blocks and body.strip():
        blocks.append(
            {
                "started": "",
                "status": classify_body(body),
                "body": body.strip(),
            }
        )
    return blocks


def query_task_scheduler(task_name: str) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        proc = subprocess.run(
            ["schtasks", "/query", "/tn", task_name, "/fo", "LIST", "/v"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0:
            out["error"] = proc.stderr.strip() or f"exit {proc.returncode}"
            return out
        for line in proc.stdout.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                out[key.strip().lower()] = val.strip()
    except Exception as exc:
        out["error"] = str(exc)
    return out


def load_logs() -> list[dict]:
    entries: list[dict] = []
    if not os.path.isdir(LOG_DIR):
        return entries
    for name in os.listdir(LOG_DIR):
        m = LOG_PATTERN.match(name)
        if not m:
            continue
        kind, ymd, hour = m.group(1), m.group(2), m.group(3)
        path = os.path.join(LOG_DIR, name)
        try:
            stat = os.stat(path)
            body = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        try:
            log_date = dt.datetime.strptime(ymd, "%Y%m%d").date()
            date_label = log_date.strftime("%A %Y-%m-%d")
            if hour:
                date_label += f" {hour}:00"
        except ValueError:
            log_date = None
            date_label = name
        status = classify_body(body)
        runs = parse_run_blocks(body)
        entries.append(
            {
                "name": name,
                "kind": kind,
                "ymd": ymd,
                "hour": hour,
                "log_date": log_date,
                "date_label": date_label,
                "mtime": dt.datetime.fromtimestamp(stat.st_mtime),
                "size": stat.st_size,
                "status": status,
                "runs": runs,
                "body": body,
                "is_thursday": log_date.weekday() == 3 if log_date else False,
                "is_today": log_date == dt.date.today() if log_date else False,
            }
        )
    entries.sort(key=lambda e: (e["ymd"], e["hour"] or "99", e["mtime"]), reverse=True)
    return entries


def status_badge(status: str, extra_class: str = "") -> str:
    colors = {
        "success": ("#d4edda", "#155724"),
        "failed": ("#f8d7da", "#721c24"),
        "skipped": ("#fff3cd", "#856404"),
        "incomplete": ("#ffe8cc", "#9a5b00"),
        "unknown": ("#e2e3e5", "#383d41"),
        "pending": ("#cce5ff", "#004085"),
    }
    bg, fg = colors.get(status, colors["unknown"])
    cls = f' class="badge {extra_class}"' if extra_class else ' class="badge"'
    return (
        f'<span{cls} style="background:{bg};color:{fg}">'
        f"{html.escape(status)}</span>"
    )


def highlight_card_classes(entry: dict, flags: set[str]) -> str:
    classes = ["log-card"]
    if entry["name"] in flags:
        classes.append("highlight")
    if entry.get("is_today"):
        classes.append("today")
    if entry.get("is_thursday") and entry["kind"] == "whatsapp_poll":
        classes.append("thursday")
    return " ".join(classes)


def format_status_row(rec: dict | None, stamp: str) -> str:
    if not rec:
        return f"No run recorded today. Last success stamp: <code>{html.escape(stamp)}</code>"
    status = rec.get("status", "?")
    attempts = rec.get("attempts", 0)
    detail = rec.get("detail", "")
    last = rec.get("last_attempt", "")
    cls = "ok" if status == "success" else "warn" if status == "failed" else ""
    return (
        f'<span class="{cls}">{html.escape(status)}</span> '
        f"(attempts={attempts}, last={html.escape(last)}, {html.escape(detail)})"
    )


def main() -> int:
    os.makedirs(LOG_DIR, exist_ok=True)
    logs = load_logs()
    now = dt.datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    poll_stamp = read_stamp(STAMP_POLL)
    turnout_stamp = read_stamp(STAMP_TURNOUT)
    poll_rec = read_status_record(STATUS_POLL)
    turnout_rec = read_status_record(STATUS_TURNOUT)
    today = now.date()
    is_thursday = today.weekday() == 3
    in_season = dt.date(today.year, 5, 12) <= today <= dt.date(today.year, 10, 30)
    in_window = 8 <= now.hour <= 23
    task_info = query_task_scheduler(POLL_TASK)

    poll_logs = [e for e in logs if e["kind"] == "whatsapp_poll"]
    today_poll_logs = [e for e in poll_logs if e.get("is_today")]
    thursday_poll_logs = [e for e in poll_logs if e.get("is_thursday")]

    highlight_names: set[str] = set()
    latest = poll_logs[0] if poll_logs else None
    if latest:
        highlight_names.add(latest["name"])
    last_thursday = thursday_poll_logs[0] if thursday_poll_logs else None
    if last_thursday and last_thursday["name"] != (latest["name"] if latest else ""):
        highlight_names.add(last_thursday["name"])
    for e in today_poll_logs:
        highlight_names.add(e["name"])

    # Today's individual run attempts across all today's log files
    today_runs: list[dict] = []
    for entry in today_poll_logs:
        for i, run in enumerate(entry.get("runs") or []):
            today_runs.append(
                {
                    "log": entry["name"],
                    "index": i + 1,
                    "started": run.get("started", ""),
                    "status": run.get("status", "unknown"),
                }
            )

    # Summary panels
    thursday_banner = ""
    if is_thursday and in_season:
        thursday_banner = (
            '<div class="thursday-banner">'
            "<strong>Today is Thursday</strong> — poll window is active "
            "(08:00–23:00, hourly retries until success)."
            "</div>"
        )

    latest_panel = '<p class="empty">No poll logs yet.</p>'
    if latest:
        latest_panel = f"""
        <div class="focus-card latest">
          <h3>Latest poll log</h3>
          <p><strong>{html.escape(latest['name'])}</strong> — {status_badge(latest['status'])}
             <span class="meta-inline">{html.escape(latest['date_label'])} · updated {latest['mtime'].strftime('%H:%M:%S')}</span></p>
          <p class="snippet">{html.escape((latest['body'] or '')[-400:])}</p>
          <a href="#{html.escape(latest['name'])}">Jump to full log ↓</a>
        </div>
        """

    last_thu_panel = ""
    if last_thursday and (
        not latest or last_thursday["name"] != latest["name"]
    ):
        last_thu_panel = f"""
        <div class="focus-card thursday-focus">
          <h3>Last Thursday poll log</h3>
          <p><strong>{html.escape(last_thursday['name'])}</strong> — {status_badge(last_thursday['status'])}
             <span class="meta-inline">{html.escape(last_thursday['date_label'])}</span></p>
          <a href="#{html.escape(last_thursday['name'])}">Jump to log ↓</a>
        </div>
        """

    today_runs_rows = ""
    if today_runs:
        for run in today_runs:
            today_runs_rows += (
                f"<tr><td>{html.escape(run['started'] or run['log'])}</td>"
                f"<td><code>{html.escape(run['log'])}</code></td>"
                f"<td>{status_badge(run['status'])}</td></tr>"
            )
    else:
        today_runs_rows = (
            '<tr><td colspan="3" class="warn">No scheduled run attempts logged today yet '
            "(Task Scheduler may have fired but logging failed, or run was blocked by IgnoreNew)."
            "</td></tr>"
        )

    task_last = task_info.get("last run time", "(unknown)")
    task_next = task_info.get("next run time", "(unknown)")
    task_status = task_info.get("status", "(unknown)")
    task_result = task_info.get("last result", "(unknown)")
    task_error = task_info.get("error", "")

    scheduler_note = ""
    if is_thursday and in_season and in_window:
        if poll_rec and poll_rec.get("status") == "success":
            scheduler_note = '<p class="ok">Poll succeeded today — further hourly runs will skip.</p>'
        elif today_runs and all(r["status"] in ("incomplete", "unknown") for r in today_runs):
            scheduler_note = (
                '<p class="warn"><strong>Runs started but did not complete.</strong> '
                "Earlier attempts may have hung after Edge CDP; hourly retries use "
                "<code>StopExisting</code> after re-installing the task.</p>"
            )
        elif not today_runs and f"{today.month}/{today.day}/" in task_last:
            scheduler_note = (
                '<p class="warn"><strong>Task Scheduler reports a run but no log was written.</strong> '
                "Re-install the task (<code>install_whatsapp_poll_task.ps1</code>) and check "
                "hourly log files <code>whatsapp_poll_YYYYMMDD_HH.log</code>.</p>"
            )

    sections = []
    for entry in logs:
        card_cls = highlight_card_classes(entry, highlight_names)
        label_bits = []
        if entry["name"] in highlight_names:
            if entry.get("is_today"):
                label_bits.append("TODAY")
            if entry.get("is_thursday"):
                label_bits.append("THURSDAY")
            if latest and entry["name"] == latest["name"]:
                label_bits.append("LATEST")
        flag_html = ""
        if label_bits:
            flag_html = (
                ' <span class="flag">'
                + " · ".join(html.escape(x) for x in label_bits)
                + "</span>"
            )
        run_count = len(entry.get("runs") or [])
        run_meta = f" · {run_count} run(s) in file" if run_count > 1 else ""
        sections.append(
            f"""
            <section class="{card_cls}" id="{html.escape(entry['name'])}">
              <div class="log-head">
                <h3>{html.escape(entry['name'])}{flag_html}</h3>
                <div class="meta">
                  {status_badge(entry['status'])}
                  <span>{html.escape(entry['date_label'])}</span>
                  <span>{entry['size']:,} bytes</span>
                  <span>updated {entry['mtime'].strftime('%Y-%m-%d %H:%M:%S')}</span>
                  <span>{run_meta}</span>
                </div>
              </div>
              <pre>{html.escape(entry['body'] or '(empty log)')}</pre>
            </section>
            """
        )

    if not sections:
        sections.append(
            '<p class="empty">No log files yet. Logs appear after scheduled or manual runs.</p>'
        )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="60">
  <title>WhatsApp Poll — Run Logs</title>
  <style>
    body {{
      max-width: 1100px; margin: 0 auto; padding: 20px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      line-height: 1.5; color: #333; background: #f7f9fc;
    }}
    h1 {{ border-bottom: 3px solid #128C7E; padding-bottom: 0.3em; }}
    .summary, .focus-card {{
      background: linear-gradient(135deg, #e8f8f4 0%, #d4f0e8 100%);
      border-left: 4px solid #128C7E; border-radius: 8px;
      padding: 16px 20px; margin: 16px 0;
    }}
    .focus-card.latest {{ border-left-color: #0d6efd; background: linear-gradient(135deg, #e7f1ff 0%, #d0e4ff 100%); }}
    .focus-card.thursday-focus {{ border-left-color: #6f42c1; background: linear-gradient(135deg, #f3ecff 0%, #e5d9ff 100%); }}
    .thursday-banner {{
      background: #6f42c1; color: #fff; padding: 12px 16px; border-radius: 8px;
      margin: 12px 0; font-size: 1.05em;
    }}
    .summary table, .runs-table {{ border-collapse: collapse; width: 100%; }}
    .summary td, .runs-table td, .runs-table th {{
      padding: 6px 8px 6px 0; vertical-align: top; border-bottom: 1px solid rgba(0,0,0,0.06);
    }}
    .summary td:first-child {{ font-weight: 600; width: 220px; color: #0d3b2e; }}
    .runs-table th {{ text-align: left; color: #0d3b2e; }}
    .warn {{ color: #9a5b00; font-weight: 600; }}
    .ok {{ color: #155724; font-weight: 600; }}
    .meta-inline {{ color: #555; font-size: 0.9em; margin-left: 8px; }}
    .snippet {{
      font-family: Consolas, monospace; font-size: 11px; background: #1e1e1e; color: #d4d4d4;
      padding: 10px; border-radius: 4px; white-space: pre-wrap; max-height: 120px; overflow: auto;
    }}
    .log-card {{
      background: #fff; border-radius: 8px; margin: 16px 0;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden;
      border: 2px solid transparent;
    }}
    .log-card.highlight {{ border-color: #0d6efd; box-shadow: 0 0 0 3px rgba(13,110,253,0.15); }}
    .log-card.today {{ border-color: #20c997; }}
    .log-card.thursday {{ border-left: 6px solid #6f42c1; }}
    .log-head {{ padding: 14px 16px; border-bottom: 1px solid #eee; }}
    .log-head h3 {{ margin: 0 0 8px 0; font-size: 1.1em; }}
    .flag {{
      display: inline-block; margin-left: 8px; padding: 2px 8px; border-radius: 4px;
      background: #ffc107; color: #333; font-size: 0.75em; font-weight: 700;
    }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 10px; font-size: 0.9em; color: #555; }}
    .badge {{ padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 0.85em; }}
    pre {{
      margin: 0; padding: 16px; background: #1e1e1e; color: #d4d4d4;
      font-size: 12px; line-height: 1.45; overflow-x: auto; white-space: pre-wrap;
    }}
    .toolbar {{ margin: 12px 0; }}
    .toolbar a {{
      display: inline-block; margin-right: 12px; color: #128C7E; font-weight: 600;
    }}
    .empty {{ padding: 24px; text-align: center; color: #666; }}
    footer {{ margin-top: 24px; font-size: 0.85em; color: #777; }}
    .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    @media (max-width: 800px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <h1>WhatsApp Poll — Run Logs</h1>
  <p>Auto-refreshes every 60 seconds. Generated {html.escape(now_str)}.</p>

  {thursday_banner}

  <div class="summary">
    <h2 style="margin-top:0">Schedule status</h2>
    <table>
      <tr><td>Today</td><td>{html.escape(today.strftime('%A %Y-%m-%d'))}</td></tr>
      <tr><td>Thursday poll window</td><td>
        {'<span class="ok">Yes — active now (08:00–23:00)</span>' if is_thursday and in_season and in_window else
         '<span class="ok">Yes — Thursday in season (08:00–23:00)</span>' if is_thursday and in_season else
         'No (not Thursday or outside May 12–Oct 30)'}
      </td></tr>
      <tr><td>Task Scheduler</td><td><code>{html.escape(POLL_TASK)}</code></td></tr>
      <tr><td>Last task run</td><td>{html.escape(task_last)} (result {html.escape(task_result)})</td></tr>
      <tr><td>Next task run</td><td>{html.escape(task_next)} (status {html.escape(task_status)})</td></tr>
      {f'<tr><td>Scheduler error</td><td class="warn">{html.escape(task_error)}</td></tr>' if task_error else ''}
      <tr><td>Last successful poll stamp</td><td><code>{html.escape(poll_stamp)}</code></td></tr>
      <tr><td>Poll status today</td><td>{format_status_row(poll_rec, poll_stamp)}</td></tr>
      <tr><td>Last turnout stamp</td><td><code>{html.escape(turnout_stamp)}</code></td></tr>
      <tr><td>Turnout status today</td><td>{format_status_row(turnout_rec, turnout_stamp)}</td></tr>
      <tr><td>Log folder</td><td><code>{html.escape(LOG_DIR)}</code></td></tr>
      <tr><td>Retention</td><td>14 days (see <code>log_rotate.py</code>)</td></tr>
    </table>
    {scheduler_note}
  </div>

  <h2>Today&apos;s run attempts ({len(today_runs)})</h2>
  <table class="runs-table summary">
    <tr><th>Started</th><th>Log file</th><th>Status</th></tr>
    {today_runs_rows}
  </table>

  <div class="grid-2">
    {latest_panel}
    {last_thu_panel}
  </div>

  <div class="toolbar">
    <a href="index.html">Refresh</a>
    <a href="../documentation/whatsapp_poll_thursday_schedule.html">Schedule guide</a>
    <a href="../documentation/whatsapp_poll_friday_turnout.html">Friday turnout</a>
    <a href="../documentation/whatsapp_poll_logs.html">About these logs</a>
  </div>

  <h2>All log files ({len(logs)})</h2>
  <p>Highlighted: <strong>TODAY</strong>, <strong>THURSDAY</strong>, <strong>LATEST</strong> poll runs.</p>
  {''.join(sections)}

  <footer>
    Open via <code>view_logs.bat</code> or file:
    <code>WhatsApp_Web_Poll\\logs\\index.html</code>
  </footer>
</body>
</html>
"""
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {OUT_FILE} ({len(logs)} logs)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
