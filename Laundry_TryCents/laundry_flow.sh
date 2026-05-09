#!/usr/bin/env bash
# Laundry TryCents order flow — pure browser-use CLI version.
#
# Stops at the Order Summary (/checkout) page so the user can review
# and submit manually.
#
# Prereq: Chrome on Windows running with --remote-debugging-port=9222.
#         start_chrome_cdp.bat handles that.
# Tab strategy: opens a NEW tab via CDP /json/new and drives that tab
#         directly via WebSocket — independent of which tab browser-use
#         considers "active". This avoids the multi-tab confusion.

set -uo pipefail

CDP_URL="${CDP_URL:-http://localhost:9222}"
ORDER_URL="${ORDER_URL:-https://app.trycents.com/new-order/N3c4/home}"
TIME_SLOT="${TIME_SLOT:-04:30PM-06:00PM}"

PYTHON_BIN="${PYTHON_BIN:-$HOME/.local/share/pipx/venvs/browser-use/bin/python}"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"

log() { printf "[laundry] %s\n" "$*"; }
fail() { log "FAIL: $*"; exit 1; }

curl -s --max-time 3 "$CDP_URL/json/version" >/dev/null
if [ $? -ne 0 ]; then
    log "CDP not reachable at $CDP_URL — attempting to start Chrome on Windows"
    SCRIPT_DIR_INIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    BAT_WIN_PATH="$(wslpath -w "$SCRIPT_DIR_INIT/start_chrome_cdp.bat" 2>/dev/null)"
    if [ -z "$BAT_WIN_PATH" ]; then
        fail "wslpath unavailable; can't launch Windows Chrome"
    fi
    cmd.exe /c "$BAT_WIN_PATH" </dev/null >/dev/null 2>&1
    # Wait up to 30s for CDP to come up
    for i in $(seq 1 30); do
        if curl -s --max-time 1 "$CDP_URL/json/version" >/dev/null 2>&1; then
            log "Chrome CDP came up after ${i}s"
            break
        fi
        sleep 1
    done
    curl -s --max-time 3 "$CDP_URL/json/version" >/dev/null \
        || fail "Chrome CDP did not come up within 30s"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRIVER="$SCRIPT_DIR/_cdp_driver.py"

CDP_URL="$CDP_URL" ORDER_URL="$ORDER_URL" TIME_SLOT="$TIME_SLOT" \
    "$PYTHON_BIN" "$DRIVER"
