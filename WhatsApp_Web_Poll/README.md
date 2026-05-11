# WhatsApp Web Poll Prototype

Minimal CDP-driven automation that posts a poll into a 1:1 WhatsApp Web
chat after finding a contact by name. Mirrors the design of
`../Laundry_TryCents/_cdp_driver.py`.

## Stack choice

**(A) CDP + existing Chrome profile** — same approach as Laundry_TryCents.
- Reuses the `C:\chrome-cdp` Chrome profile that's already signed into
  WhatsApp Web (manual one-time login).
- Script attaches to `http://localhost:9222` and drives a tab via
  WebSocket / `Runtime.evaluate`.
- No Selenium, no Playwright, no `browser-use` — `urllib` + `websocket-client` only.

We did **not** use Playwright because (a) it would need a separate
profile that re-scans the WhatsApp QR each time and (b) sharing one
already-logged-in Chrome with the rest of the CDP automation in this
workspace is more convenient.

## Files

- `whatsapp_poll.py` — the driver (pure Python, ~250 lines)
- `start_chrome_cdp.bat` — boots Chrome with CDP if not already running
- `run_whatsapp_poll.bat` — single-click launcher (Windows)
- `requirements.txt` — `websocket-client` (already provided by the
  `browser-use` venv on this machine)
- `README.md` — this file

## Prereqs

1. Chrome on Windows installed at `C:\Program Files\Google\Chrome\Application\chrome.exe`.
2. The `C:\chrome-cdp` profile signed-in to **web.whatsapp.com** (one-time:
   open WhatsApp Web in that profile, scan the QR with your phone, wait for
   the chat list to fully load, then close the window).
3. WSL with Python and `websocket-client` available. The shipped batch
   file uses `~/.local/share/pipx/venvs/browser-use/bin/python` because
   that venv already has `websocket-client`. If you don't have that path,
   create any venv with `pip install websocket-client` and edit the
   `.bat` to point at its `python`.

## How to run

**Dry run (default — fills the poll but does NOT click Send):**

Double-click `run_whatsapp_poll.bat`, or from cmd:

    cd C:\E_Drive\project_workspace\tasks_automation\WhatsApp_Web_Poll
    run_whatsapp_poll.bat

You'll see the poll composer pop up in Chrome with the question and
options filled in. Verify it looks right.

**Real send (after confirming the dry run):**

    set SEND=1
    run_whatsapp_poll.bat

**On WSL directly (no Windows batch):**

    SEND=1 ~/.local/share/pipx/venvs/browser-use/bin/python \
        /mnt/c/E_Drive/project_workspace/tasks_automation/WhatsApp_Web_Poll/whatsapp_poll.py

## Env variables

| Var | Default | Purpose |
|---|---|---|
| `CDP_URL`    | `http://localhost:9222` | Chrome remote debugging endpoint |
| `CONTACT`    | `Joseph` | Chat recipient display name (case-insensitive substring) |
| `POLL_TITLE` | (see source) | Override the poll question |
| `SEND`       | unset | Set `1` to actually click the Send button |
| `TRACE`      | unset | Set `1` to dump DOM info at the step where it fails (use this when WhatsApp updates and a selector breaks) |

## Poll content (defaults)

**Question:**

> Friday 6:00 PM at Lake Hiawatha Park — https://g.co/kgs/FrFYPm8
> Hosted by Parsippany Rescue & Recovery Unit.
> Please confirm by noon Friday.

**Options:** `Yes`, `No`.

WhatsApp's poll composer supports "Allow multiple answers" — we leave it
at the WhatsApp default (single answer). To toggle multi-select,
manually flip the switch in the composer during the dry-run pass; we
can wire that up later if you want it always-on.

## Known limitations

- **WhatsApp Web markup changes regularly.** Selectors in
  `whatsapp_poll.py` are written defensively (multiple fallbacks per
  step) but expect to update them every few months. Use `TRACE=1` to
  see the live DOM at the failing step, then refine that selector.
- **No official API for personal WhatsApp polls.** This is pure UI
  automation. Meta does not endorse it; in extreme cases automated
  patterns can flag an account. Keep usage modest and human-paced.
- **Contact matching is by display name.** If you have multiple chats
  whose names contain "Joseph" the first match wins. Use the full
  exact name in `CONTACT` if ambiguous.
- **DRY-RUN does not undo the typing.** The dry run leaves the poll
  composer open with text filled in. You can either click Send
  manually, or press Escape and re-run.
- **First load can be slow** (60s timeout for the sidebar to appear) if
  your WhatsApp Web hasn't finished syncing since last open.

## Non-goals (v1)

- Hermes cron scheduling (can be added later — same wrapper pattern as
  `~/.hermes/scripts/laundry_trycents_weekly.sh`).
- Mobile-app automation.
- WhatsApp Business API.
- Group chats (works for 1:1 only; group selectors differ).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Chrome CDP unreachable` | Run `start_chrome_cdp.bat`. Fully quit any other Chrome first (all `chrome.exe` in Task Manager). |
| Hangs waiting for "WhatsApp Web sidebar" | The profile isn't signed in. Open `C:\chrome-cdp` Chrome, navigate to web.whatsapp.com, scan the QR with your phone, wait for chats to load, then re-run. |
| "could not click: Poll" | WhatsApp moved the menu. Run with `TRACE=1`, inspect the dumped ARIA labels, update `S_POLL_MENU_ITEM` in `whatsapp_poll.py`. |
| Wrong chat opens | Make `CONTACT` more specific (full name) or check for a similarly-named chat above Joseph in the list. |
