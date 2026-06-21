# Laundry TryCents Automation (CDP + Microsoft Edge)

Automates the wash-and-fold + Gain detergent + 04:30PM pickup order
on app.trycents.com, driving **Microsoft Edge** on your Windows desktop
via the Chrome DevTools Protocol (CDP).

## Files

- `start_edge_cdp.bat` — boots Edge with `--remote-debugging-port=9222`
  if not already running. Profile lives at `C:\edge-cdp-laundry` so you stay
  logged in to TryCents across runs.
- `start_chrome_cdp.bat` — deprecated; forwards to `start_edge_cdp.bat`
- `laundry_flow.sh` — bash entry point (WSL). Verifies CDP is up and runs the driver.
- `_cdp_driver.py` — pure stdlib + `websocket-client` driver. Opens a
  brand-new Edge tab, pins to it by id, drives via CDP `Runtime.evaluate`.
  No Selenium, no Playwright, no browser-use.
- `run_laundry.bat` — single-click launcher: ensures Edge is up, runs the flow.

## One-time setup

1. Close all Edge and Chrome windows (port 9222 must be free).
2. Run `start_edge_cdp.bat` — Edge opens TryCents with profile `C:\edge-cdp-laundry`.
3. Log in to TryCents once; session persists in that profile.

**Note:** WhatsApp poll automation uses a separate profile (`C:\edge-cdp`).
Only one browser can own port 9222 — quit the other automation’s browser before running laundry.

## Usage

Double-click `run_laundry.bat` (or run from cmd / PowerShell).

The script stops at the Order Summary page (`/checkout`) — review the
order in Edge and click Submit yourself.

**WSL:** `bash laundry_flow.sh` from this folder (still supported).

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

The CDP driver only needs `websocket-client` (`pip install websocket-client`).
