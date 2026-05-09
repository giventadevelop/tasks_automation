# Laundry TryCents Automation (CDP)

Automates the wash-and-fold + Gain detergent + 04:30PM pickup order
on app.trycents.com, driving the Chrome browser already running on
your Windows desktop via the Chrome DevTools Protocol.

## Files

- `start_chrome_cdp.bat` — boots Chrome with `--remote-debugging-port=9222`
  if not already running. Profile lives at `C:\chrome-cdp` so you stay
  logged in across runs.
- `laundry_flow.sh` — bash entry point (called from WSL). Verifies CDP
  is up and runs the Python driver.
- `_cdp_driver.py` — pure stdlib + `websocket-client` driver. Opens a
  brand-new Chrome tab, pins to it by id, drives via CDP `Runtime.evaluate`.
  No Selenium, no Playwright, no browser-use.
- `run_laundry.bat` — single-click launcher: ensures Chrome is up, runs
  the flow.

## Usage

Double-click `run_laundry.bat` (or run from cmd / PowerShell).

The script stops at the Order Summary page (`/checkout`) — review the
order and click Submit yourself.

## Customizing

Set environment variables (or edit the defaults in `_cdp_driver.py`):

  ORDER_URL   default: https://app.trycents.com/new-order/N3c4/home
  TIME_SLOT   default: 04:30PM-06:00PM
  CDP_URL     default: http://localhost:9222

The slot picker advances day-by-day until it finds the target slot
(up to 7 days), so it works whether your preferred time is available
today or several days out.

## Legacy files (kept for reference)

- `laundry_automation.py` — old Selenium version (slow profile-copy approach)
- `laundry_auto_ui_vision_regular_flow.json` — UI.Vision macro
- `requirements.txt` — Selenium deps (no longer needed)

The CDP driver only needs `websocket-client` (already installed in
the browser-use venv on this machine).
