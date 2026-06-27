#!/usr/bin/env python3
"""WhatsApp Web poll automation via CDP-attached Chromium browser (Edge or Chrome).

Strategy mirrors Laundry_TryCents/_cdp_driver.py:
  * Attaches to Edge/Chrome already running with --remote-debugging-port=9222
  * Finds (or opens) the web.whatsapp.com tab and drives it via WebSocket
  * Clicks Log in on the landing page if the profile is not yet authenticated
  * No Selenium / Playwright / browser-use — stdlib + websocket-client only

Safety: defaults to DRY-RUN (fills the poll but does NOT click Send).
        Set env SEND=1 to actually send.

Env vars:
  CDP_URL    default http://localhost:9222
  CONTACT    default "Volleyball Friday"
  POLL_TITLE override the question text
  CANCEL_MSG / TEMP_CANCEL_MSG  cancellation texts for rain / temperature
  LOW_TURNOUT_MSG               not-enough-players cancellation text
  GO_MSG                        all-clear message when weather + turnout OK (Friday)
  MIN_PLAYERS                   minimum Yes votes (default 6)
  ACTION                        poll (default) | check_turnout | send_low_turnout_cancel
  SEND       "1" to actually click Send; anything else = dry run
  TRACE      "1" dumps DOM snapshots on failure (helpful first time)
  SKIP_WEATHER  "1" skips the weather pre-check entirely
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

import websocket  # provided by the browser-use venv on this machine

from run_status import mark_success as mark_turnout_success


CDP_URL = os.environ.get("CDP_URL", "http://localhost:9222")
DEFAULT_TITLE = (
    "Shall we play Volleyball this Friday 6:00 PM at Lake Hiawatha Park — https://g.co/kgs/FrFYPm8\n"
    "📍 4 Volunteers Court, Lake Hiawatha, NJ 07034\n"
    "Near to 'Parsippany Rescue & Recovery Unit'.\n"
    "Please confirm by noon Friday."
)
DEFAULT_CANCEL_MSG = (
    "🌧️ Rainy day — volleyball cancelled this Friday. We'll regroup next week."
)
DEFAULT_TEMP_CANCEL_MSG = (
    "🌡️ Temperature outside playable range (65–92°F) — "
    "volleyball cancelled this Friday. We'll regroup next week."
)
DEFAULT_LOW_TURNOUT_MSG = (
    "Today's volleyball game CANCELED : Not enough people\n\n"
    "Hey folks, today's volleyball game at the park's off—doesn't look like we've got "
    "enough people. No worries, we'll aim for next week. Catch you then!"
)
DEFAULT_GO_MSG = (
    "✅ Everything looks good!\n\n"
    "Both the weather and the number of people are good for today's volleyball at the park. "
    "Let's play! See you at Lake Hiawatha — 6:00 PM."
)
POLL_TITLE = os.environ.get("POLL_TITLE", DEFAULT_TITLE)
CANCEL_MSG = os.environ.get("CANCEL_MSG", DEFAULT_CANCEL_MSG)
TEMP_CANCEL_MSG = os.environ.get("TEMP_CANCEL_MSG", DEFAULT_TEMP_CANCEL_MSG)
LOW_TURNOUT_MSG = os.environ.get("LOW_TURNOUT_MSG", DEFAULT_LOW_TURNOUT_MSG)
GO_MSG = os.environ.get("GO_MSG", DEFAULT_GO_MSG)
MIN_PLAYERS = int(os.environ.get("MIN_PLAYERS", "6"))
ACTION = os.environ.get("ACTION", "poll").strip().lower()
POLL_OPTIONS = ["Yes", "No"]
SEND = os.environ.get("SEND", "") == "1"
TRACE = os.environ.get("TRACE", "") == "1"
SCHEDULED = os.environ.get("SCHEDULED", "") == "1"
SESSION_TIMEOUT_SEC = int(
    os.environ.get("SESSION_TIMEOUT_SEC", "300" if SCHEDULED else "120")
)
POST_READY_SETTLE_SEC = int(
    os.environ.get("POST_READY_SETTLE_SEC", "25" if SCHEDULED else "8")
)
PRE_SEARCH_SETTLE_SEC = int(
    os.environ.get("PRE_SEARCH_SETTLE_SEC", "5" if SCHEDULED else "2")
)
MIN_CHAT_ROWS = int(os.environ.get("MIN_CHAT_ROWS", "1" if SCHEDULED else "3"))


# Default contact (used when env var is unset OR empty).
DEFAULT_CONTACT = "Volleyball Friday"
CONTACT = os.environ.get("CONTACT", "").strip() or DEFAULT_CONTACT


# ---- Weather pre-check ----------------------------------------------------
# Location: Lake Hiawatha Park, NJ (≈4 Volunteers Court, Lake Hiawatha 07034)
WEATHER_LOCATION = os.environ.get("WEATHER_LOCATION", "Lake Hiawatha, NJ")
WEATHER_LAT = float(os.environ.get("WEATHER_LAT", "40.881"))
WEATHER_LON = float(os.environ.get("WEATHER_LON", "-74.387"))
# NWS reports a nearest city name (often Boonton for this grid); coords are the real location check
WEATHER_LOCATION_KEYWORDS = tuple(
    k.strip().lower()
    for k in os.environ.get(
        "WEATHER_LOCATION_KEYWORDS",
        "lake hiawatha,hiawatha,parsippany,boonton,montville,troy hills",
    ).split(",")
    if k.strip()
)
# Volleyball season: May 12 through October 30 (inclusive), local calendar dates
SEASON_START_MONTH = int(os.environ.get("SEASON_START_MONTH", "5"))
SEASON_START_DAY = int(os.environ.get("SEASON_START_DAY", "12"))
SEASON_END_MONTH = int(os.environ.get("SEASON_END_MONTH", "10"))
SEASON_END_DAY = int(os.environ.get("SEASON_END_DAY", "30"))
# Window we care about (tomorrow, local time): 4 PM – 8 PM
WEATHER_WINDOW_START_HOUR = int(os.environ.get("WEATHER_START_HOUR", "16"))
WEATHER_WINDOW_END_HOUR = int(os.environ.get("WEATHER_END_HOUR", "20"))
# Playable temperature range (°F) during the game window
TEMP_MIN_F = int(os.environ.get("TEMP_MIN_F", "65"))
TEMP_MAX_F = int(os.environ.get("TEMP_MAX_F", "92"))
# Rain decision thresholds
RAIN_KEYWORDS = ("rain", "shower", "thunderstorm", "storm", "drizzle")
RAIN_POP_THRESHOLD = int(os.environ.get("RAIN_POP_THRESHOLD", "50"))  # %
# Skip the weather pre-check entirely (e.g. for indoor events / debugging)
SKIP_WEATHER = os.environ.get("SKIP_WEATHER", "") == "1"


def log(msg: str) -> None:
    out = f"[wapoll] {msg}"
    try:
        print(out, flush=True)
    except UnicodeEncodeError:
        print(out.encode("ascii", errors="replace").decode("ascii"), flush=True)


def fail(msg: str) -> None:
    log(f"FAIL: {msg}")
    sys.exit(1)


def _http(method: str, path: str, timeout: float = 10) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(f"{CDP_URL}{path}", method=method), timeout=timeout
    ).read()


# ---- Weather check helpers ------------------------------------------------

def _nws_get(url: str, timeout: float = 15) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "WhatsApp_Web_Poll/1.0 (personal volleyball poll)",
            "Accept": "application/geo+json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _in_volleyball_season(d: "datetime.date") -> bool:
    import datetime as _dt

    start = _dt.date(d.year, SEASON_START_MONTH, SEASON_START_DAY)
    end = _dt.date(d.year, SEASON_END_MONTH, SEASON_END_DAY)
    return start <= d <= end


def _location_matches_nws(points: dict) -> tuple[bool, str]:
    """Return (ok, resolved_label) for the NWS grid point.

    Lake Hiawatha is identified by WEATHER_LAT/WEATHER_LON. NWS only supplies a
    nearest city label (commonly Boonton or Parsippany for this grid).
    """
    rel = (points.get("properties") or {}).get("relativeLocation") or {}
    city = ((rel.get("properties") or {}).get("city") or "").strip()
    state = ((rel.get("properties") or {}).get("state") or "").strip()
    label = f"{city}, {state}".strip(", ")
    if state and state.upper() != "NJ":
        return False, label
    if city:
        city_l = city.lower()
        if not any(kw in city_l for kw in WEATHER_LOCATION_KEYWORDS):
            log(
                f"weather: NWS nearest city is {label!r}; "
                f"using forecast for {WEATHER_LOCATION} at ({WEATHER_LAT},{WEATHER_LON})"
            )
    return True, label or WEATHER_LOCATION


def weather_check_for_date(target: "datetime.date") -> tuple[str, str, str]:
    """Return (decision, human_message, cancel_reason) for target date game window."""
    import datetime as _dt

    if not _in_volleyball_season(target):
        return (
            "skip",
            (
                f"weather: {target.isoformat()} is outside volleyball season "
                f"({SEASON_START_MONTH:02d}/{SEASON_START_DAY:02d}-"
                f"{SEASON_END_MONTH:02d}/{SEASON_END_DAY:02d})"
            ),
            "",
        )

    log(
        f"weather: fetching forecast for {WEATHER_LOCATION} "
        f"({WEATHER_LAT},{WEATHER_LON})"
    )
    points = _nws_get(f"https://api.weather.gov/points/{WEATHER_LAT},{WEATHER_LON}")
    loc_ok, nws_label = _location_matches_nws(points)
    if not loc_ok:
        return (
            "skip",
            (
                f"weather: NWS grid point resolved to {nws_label!r}, "
                f"expected area near {WEATHER_LOCATION} — skipping"
            ),
            "",
        )

    forecast_url = points["properties"]["forecastHourly"]
    forecast = _nws_get(forecast_url)
    periods = forecast["properties"]["periods"]

    relevant = []
    for p in periods:
        st = _dt.datetime.fromisoformat(p["startTime"])
        if st.date() != target:
            continue
        if not (WEATHER_WINDOW_START_HOUR <= st.hour < WEATHER_WINDOW_END_HOUR):
            continue
        pop = (p.get("probabilityOfPrecipitation") or {}).get("value") or 0
        fc = p.get("shortForecast", "")
        temp = p.get("temperature")
        temp_unit = (p.get("temperatureUnit") or "F").upper()
        if temp is not None and temp_unit != "F":
            temp = int(round(temp * 9 / 5 + 32))
        rainy = pop >= RAIN_POP_THRESHOLD or any(k in fc.lower() for k in RAIN_KEYWORDS)
        temp_ok = temp is not None and TEMP_MIN_F <= temp <= TEMP_MAX_F
        relevant.append({
            "hour": st.strftime("%I:%M %p").lstrip("0"),
            "pop": pop,
            "temp": temp,
            "forecast": fc,
            "rainy": rainy,
            "temp_ok": temp_ok,
        })

    if not relevant:
        return (
            "proceed",
            f"weather: no forecast data for {target.isoformat()} window — proceeding",
            "",
        )

    rainy_hours = [r for r in relevant if r["rainy"]]
    bad_temp_hours = [r for r in relevant if r["temp"] is not None and not r["temp_ok"]]
    lines = [
        f"  {r['hour']}: {r['pop']}%"
        + (f", {r['temp']}°F" if r["temp"] is not None else "")
        + f" — {r['forecast']}"
        for r in relevant
    ]
    summary = (
        f"weather check for {WEATHER_LOCATION} ({nws_label}), "
        f"{target.isoformat()} "
        f"{WEATHER_WINDOW_START_HOUR:02d}:00-{WEATHER_WINDOW_END_HOUR:02d}:00 local:\n"
        + "\n".join(lines)
    )

    if rainy_hours:
        return (
            "cancel",
            summary + (
                f"\n→ RAIN expected ({len(rainy_hours)} of {len(relevant)} hours flagged). "
                "Game cancelled due to weather."
            ),
            "rain",
        )

    if bad_temp_hours:
        temps = [r["temp"] for r in bad_temp_hours if r["temp"] is not None]
        return (
            "cancel",
            summary + (
                f"\n→ Temperature outside {TEMP_MIN_F}-{TEMP_MAX_F}°F "
                f"({len(bad_temp_hours)} of {len(relevant)} hours flagged"
                + (f"; range {min(temps)}-{max(temps)}°F" if temps else "")
                + "). Game cancelled due to weather."
            ),
            "temp",
        )

    return (
        "proceed",
        summary + (
            f"\n→ no rain expected and temps within {TEMP_MIN_F}-{TEMP_MAX_F}°F "
            "— weather OK for game."
        ),
        "",
    )


def weather_check_tomorrow() -> tuple[str, str, str]:
    """Return (decision, human_message, cancel_reason) for tomorrow's game window."""
    import datetime as _dt

    tomorrow = (_dt.datetime.now().astimezone() + _dt.timedelta(days=1)).date()
    return weather_check_for_date(tomorrow)


def weather_check_today() -> tuple[str, str, str]:
    """Return (decision, human_message, cancel_reason) for today's game window (Friday turnout)."""
    import datetime as _dt

    return weather_check_for_date(_dt.datetime.now().astimezone().date())


def list_tabs() -> list:
    return [t for t in json.loads(_http("GET", "/json/list")) if t.get("type") == "page"]


def open_tab(url: str) -> dict:
    return json.loads(_http("PUT", f"/json/new?{url}"))


def activate_tab(tab_id: str) -> None:
    """Bring the CDP target tab to the foreground in Edge/Chrome."""
    try:
        urllib.request.urlopen(
            urllib.request.Request(f"{CDP_URL}/json/activate/{tab_id}", method="GET"),
            timeout=5,
        )
    except Exception as exc:
        log(f"tab activate: {exc}")


def find_or_open_whatsapp() -> dict:
    for t in list_tabs():
        if "web.whatsapp.com" in t.get("url", ""):
            log(f"found existing WhatsApp tab {t['id'][:8]}  {t['url']}")
            activate_tab(t["id"])
            time.sleep(0.5)
            # Re-list so webSocketDebuggerUrl is fresh (avoids stale CDP connections).
            for fresh in list_tabs():
                if fresh.get("id") == t["id"]:
                    return fresh
            return t
    log("no WhatsApp tab — opening new one")
    tab = open_tab("https://web.whatsapp.com/")
    activate_tab(tab["id"])
    time.sleep(0.5)
    return tab


class Tab:
    """Thin wrapper around CDP Runtime.evaluate + Input.* on one tab."""

    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self._id = 0
        try:
            self._call("Page.bringToFront", timeout=5)
        except Exception:
            pass

    def _recv_json(self, deadline: float) -> dict | None:
        """Read one CDP message; return None on socket timeout."""
        remaining = deadline - time.time()
        if remaining <= 0:
            return None
        self.ws.settimeout(max(0.05, remaining))
        try:
            return json.loads(self.ws.recv())
        except websocket.WebSocketTimeoutException:
            return None

    def _call(self, method: str, params: dict | None = None, timeout: float = 15):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = self._recv_json(deadline)
            if r is None:
                continue
            if r.get("id") == mid:
                if "error" in r:
                    raise RuntimeError(r["error"])
                return r.get("result")
        raise TimeoutError(f"CDP timeout: {method}")

    def eval(self, expr: str, timeout: float = 15):
        stripped = expr.strip()
        # Avoid double-wrapping IIFEs — an outer ()=>{} block does not return
        # the inner IIFE's value, which broke S_CHATS_FULLY_LOADED (always None).
        if (
            (stripped.startswith("(()=>") or stripped.startswith("(function"))
            and stripped.endswith(")()")
        ):
            expression = stripped
        else:
            expression = f"(()=>{{{expr}}})()"
        r = self._call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": False,
            },
            timeout,
        )
        res = r.get("result", {})
        if res.get("subtype") == "error":
            raise RuntimeError(res.get("description", "JS error"))
        return res.get("value")

    def wait(self, expr: str, label: str, timeout: float = 30, poll: float = 0.5):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            try:
                last = self.eval(f"return ({expr});")
                if last:
                    return last
            except Exception as exc:
                last = f"err:{exc}"
            time.sleep(poll)
        if TRACE:
            self._dump_dom_summary(label)
        fail(f"timeout waiting for: {label} (last={last!r})")

    def click(self, selector_js: str, label: str, timeout: float = 15):
        """Click by dispatching real mouse events at the element's center.
        Falls back to el.click() if coords can't be obtained.
        Some web apps (notably WhatsApp Web) ignore synthetic el.click() and
        require actual Input.dispatchMouseEvent."""
        expr = (
            f"const el=({selector_js});"
            "if(!el) return null;"
            "el.scrollIntoView({block:'center'});"
            "const r=el.getBoundingClientRect();"
            "return {x:r.x+r.width/2, y:r.y+r.height/2, ok:r.width>0&&r.height>0};"
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                pos = self.eval(expr)
                if pos and pos.get("ok"):
                    x, y = pos["x"], pos["y"]
                    self._call("Input.dispatchMouseEvent",
                               {"type": "mouseMoved", "x": x, "y": y})
                    self._call("Input.dispatchMouseEvent",
                               {"type": "mousePressed", "x": x, "y": y,
                                "button": "left", "clickCount": 1})
                    self._call("Input.dispatchMouseEvent",
                               {"type": "mouseReleased", "x": x, "y": y,
                                "button": "left", "clickCount": 1})
                    log(f"clicked: {label}")
                    return
            except Exception as exc:
                log(f"click err on '{label}': {exc}")
            time.sleep(0.4)
        if TRACE:
            self._dump_dom_summary(label)
        fail(f"could not click: {label}")

    def focus(self, selector_js: str, label: str, timeout: float = 10):
        expr = (
            f"const el=({selector_js});"
            "if(!el) return false;"
            "el.focus();"
            "if(typeof el.click==='function' && document.activeElement!==el){el.click();}"
            "return document.activeElement===el || true;"
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.eval(expr):
                    log(f"focused: {label}")
                    return
            except Exception as exc:
                log(f"focus err on '{label}': {exc}")
            time.sleep(0.4)
        fail(f"could not focus: {label}")

    def insert_text(self, text: str) -> None:
        """Insert text into the currently focused element.

        Strategy: try CDP Input.insertText first (works for both contenteditable
        and most <input> elements via the input event). Only fall back to
        direct value-setter or char-by-char typing if insertText raises.

        Earlier versions had a post-insert verification that compared
        innerText/value to the typed text; that gave false negatives for
        contenteditable (text inserted as nested spans, innerText timing) and
        caused fallbacks to run on top of the first insert — doubling chars.
        """
        # Strategy 1 — Input.insertText (the right tool for the job)
        try:
            self._call("Input.insertText", {"text": text}, timeout=10)
            return
        except Exception as exc:
            log(f"insertText failed ({exc}); trying fallbacks")

        # Strategy 2 — direct value setter (only useful for native <input>/<textarea>)
        try:
            ok = self.eval(
                "const el=document.activeElement;"
                "if(!el || !('value' in el)) return false;"
                "const proto=Object.getPrototypeOf(el);"
                "const desc=Object.getOwnPropertyDescriptor(proto,'value');"
                "if(!desc||!desc.set) return false;"
                f"desc.set.call(el, {json.dumps(text)});"
                "el.dispatchEvent(new Event('input',{bubbles:true}));"
                "el.dispatchEvent(new Event('change',{bubbles:true}));"
                "return true;"
            )
            if ok:
                return
        except Exception as exc:
            log(f"value-set fallback failed: {exc}")

        # Strategy 3 — last resort: type each char
        log(f"falling back to char-by-char typing for {text!r}")
        for ch in text:
            if ch == "\n":
                self.press_key("Enter", "Enter", 13)
            else:
                self._call("Input.dispatchKeyEvent",
                           {"type": "keyDown", "text": ch, "key": ch, "unmodifiedText": ch})
                self._call("Input.dispatchKeyEvent",
                           {"type": "char", "text": ch, "key": ch, "unmodifiedText": ch})
                self._call("Input.dispatchKeyEvent",
                           {"type": "keyUp", "text": ch, "key": ch, "unmodifiedText": ch})

    def press_key(self, key: str, code: str | None = None, win_vk: int | None = None) -> None:
        params = {"type": "keyDown", "key": key}
        if code:
            params["code"] = code
        if win_vk:
            params["windowsVirtualKeyCode"] = win_vk
        self._call("Input.dispatchKeyEvent", params)
        params["type"] = "keyUp"
        self._call("Input.dispatchKeyEvent", params)

    def _dump_dom_summary(self, label: str) -> None:
        try:
            summary = self.eval(
                "return JSON.stringify({"
                "url:location.href,"
                "title:document.title,"
                "bodyLen:document.body.innerText.length,"
                "ariaLabeledClickables:[...document.querySelectorAll('[aria-label]')]"
                ".filter(e=>e.offsetParent!==null)"
                ".slice(0,40)"
                ".map(e=>({a:e.getAttribute('aria-label'),tag:e.tagName,role:e.getAttribute('role')}))"
                "});"
            )
            log(f"--- DOM dump at '{label}' ---")
            log(summary or "(empty)")
        except Exception as exc:
            log(f"DOM dump failed: {exc}")

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


# ---- Selectors -------------------------------------------------------------
# All selectors are written defensively — each step has multiple fallbacks.
# When WhatsApp Web changes, update these here.

S_CHAT_LIST = "document.querySelector('div[role=\"grid\"][aria-label*=\"Chat\"], #pane-side')"
S_LOGGED_IN = (
    "const side=document.querySelector("
    "'#pane-side, #side, [data-testid=\"chat-list\"], [data-testid=\"chatlist-panel\"]'"
    ");"
    "if(!side) return false;"
    "const search=[...document.querySelectorAll("
    "'input, [role=\"textbox\"], div[contenteditable=\"true\"]'"
    ")].find(e=>{"
    "  const al=(e.getAttribute('aria-label')||'').toLowerCase();"
    "  return al.includes('search') || e.getAttribute('data-tab')==='3';"
    "});"
    "const rows=side.querySelectorAll("
    "'[role=\"listitem\"], [role=\"row\"], [data-testid=\"cell-frame-container\"], div[role=\"gridcell\"]'"
    ");"
    "return rows.length>0 || !!search;"
)
S_CHATS_FULLY_LOADED = (
    f"const minRows={MIN_CHAT_ROWS};"
    "const side=document.querySelector("
    "'#pane-side, #side, [data-testid=\"chat-list\"], [data-testid=\"chatlist-panel\"]'"
    ");"
    "if(!side) return {ready:false, reason:'no_sidebar'};"
    "const rows=side.querySelectorAll("
    "'[role=\"listitem\"], [role=\"row\"], [data-testid=\"cell-frame-container\"], div[role=\"gridcell\"]'"
    ");"
    "const search=document.querySelector('[data-testid=\"chat-list-search\"]')"
    "||[...document.querySelectorAll("
    "'input, [role=\"textbox\"], div[contenteditable=\"true\"]'"
    ")].find(e=>{"
    "  if(!e.offsetParent) return false;"
    "  const al=(e.getAttribute('aria-label')||'').toLowerCase();"
    "  const ph=(e.getAttribute('placeholder')||'').toLowerCase();"
    "  return al.includes('search') || ph.includes('search') || e.getAttribute('data-tab')==='3';"
    "});"
    "if(!search && rows.length<minRows) return {ready:false, reason:'no_search', rows:rows.length};"
    "if(rows.length<minRows) return {ready:false, reason:'chats_loading', rows:rows.length};"
    "const busy=!!document.querySelector("
    "'[role=\"progressbar\"], [data-testid=\"alert-phone\"], "
    "[data-icon=\"progress-spinner\"], [data-testid=\"startup-clocks\"]'"
    ");"
    "if(busy) return {ready:false, reason:'syncing', rows:rows.length};"
    "return {ready:true, rows:rows.length};"
)
S_WHATSAPP_STATE = (
    "if(document.querySelector("
    "'#pane-side [role=\"listitem\"], #pane-side [role=\"row\"], "
    "[data-testid=\"chat-list\"] [role=\"row\"], [data-testid=\"cell-frame-container\"]'"
    ")) return 'ready';"
    "if(document.querySelector("
    "'canvas[aria-label], [data-testid=\"qrcode\"], "
    "[data-testid=\"link-device-qrcode\"]'"
    ")) return 'qr';"
    "if(document.querySelector("
    "'[data-testid=\"landing-wrapper\"], [data-testid=\"intro-md-beta-logo-light\"], "
    "[data-asset-intro-image-light]'"
    ")) return 'landing';"
    "if(document.querySelector('#pane-side, #side, #app')) return 'loading';"
    "return 'unknown';"
)
S_LOGIN_BUTTON = (
    "(()=>{"
    "const vis=e=>e&&e.offsetParent!==null;"
    "const cands=[...document.querySelectorAll('a, button, div[role=\"button\"]')]"
    ".filter(vis);"
    "return cands.find(e=>/log in with phone|log in|link with phone/i.test("
    "(e.innerText||'').trim())) || null;"
    "})()"
)
S_LANDING_PAGE = (
    "document.querySelector('[data-testid=\"landing-wrapper\"], "
    "[data-testid=\"intro-md-beta-logo-light\"], "
    "[data-asset-intro-image-light]')"
)
# ---- Chat-list search locator ---------------------------------------------
# WhatsApp Web changes the search field shape every few months. Rather than
# chase one selector, we try several strategies in priority order. Each
# returns the element (or null) and the FIRST non-null wins. If ALL fail, we
# auto-dump every plausible candidate so the next fix is one selector edit.
#
# Strategies (most → least specific):
#   1. Exact aria-label "Search or start a new chat" (current, May 2026)
#   2. Any aria-label / placeholder matching /search/i  (covers renames + i18n
#      English variants like "Search chats", "Search input textbox")
#   3. data-tab="3" — historical WA hook for the chat-search box
#   4. role="textbox" placed inside or directly above #pane-side (chat list)
#   5. Geometric heuristic: any visible <input> / contenteditable in the
#      top-left strip (x<700, y<220, width>100) — language-neutral
#
# This means even if WhatsApp removes aria-labels entirely, strategy 5 still
# finds the right element by position. If they move it to the right pane,
# strategies 1–3 still match by label.
_SEARCH_INPUT_EXPR = (
    "(()=>{"
    "const vis=e=>e && e.offsetParent!==null;"
    # ---- 1) exact known aria-label ----
    "let a=document.querySelector('input[aria-label=\"Search or start a new chat\"], "
    "[role=\"textbox\"][aria-label=\"Search or start a new chat\"]');"
    "if(vis(a)) return a;"
    # ---- 2) any aria-label/placeholder matching /search/i ----
    "const all=[...document.querySelectorAll('input, [role=\"textbox\"], div[contenteditable=\"true\"]')]"
    ".filter(vis);"
    "const byLabel=all.find(e=>{"
    "  const al=(e.getAttribute('aria-label')||'')+'|'+(e.getAttribute('placeholder')||'')"
    "          +'|'+(e.getAttribute('title')||'');"
    "  return /search/i.test(al);"
    "});"
    "if(byLabel) return byLabel;"
    # ---- 3) data-tab=\"3\" (legacy hook) ----
    "const dt=document.querySelector('[data-tab=\"3\"]');"
    "if(vis(dt)) return dt;"
    # ---- 4) role=textbox living near the chat-list pane ----
    "const pane=document.querySelector('#pane-side');"
    "if(pane){"
    "  const paneR=pane.getBoundingClientRect();"
    "  const near=all.find(e=>{"
    "    const r=e.getBoundingClientRect();"
    "    return r.x>=paneR.x-20 && r.x<=paneR.right && r.y<paneR.y+20 && r.width>100;"
    "  });"
    "  if(near) return near;"
    "}"
    # ---- 5) geometric heuristic: top-left visible text input ----
    "const tl=all.filter(e=>{"
    "  const r=e.getBoundingClientRect();"
    "  return r.x<700 && r.y<220 && r.width>100;"
    "});"
    "return tl[0] || null;"
    "})()"
)
S_SEARCH_BUTTON = _SEARCH_INPUT_EXPR
S_SEARCH_BOX = _SEARCH_INPUT_EXPR

# Diagnostic helper: when the search field can't be found, dump everything
# that LOOKS like an input on the page so we can update the locator in
# ONE edit. Called automatically from open_contact_chat() on failure.
_SEARCH_DIAG_EXPR = (
    "(()=>{"
    "const all=[...document.querySelectorAll('input, [role=\"textbox\"], div[contenteditable=\"true\"]')]"
    ".filter(e=>e.offsetParent!==null);"
    "return JSON.stringify(all.slice(0,30).map(e=>{"
    "  const r=e.getBoundingClientRect();"
    "  return {tag:e.tagName, type:e.getAttribute('type'), role:e.getAttribute('role'),"
    "          aria:e.getAttribute('aria-label'), ph:e.getAttribute('placeholder'),"
    "          title:e.getAttribute('title'), dataTab:e.getAttribute('data-tab'),"
    "          ce:e.getAttribute('contenteditable'),"
    "          x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width), h:Math.round(r.height)};"
    "}));"
    "})()"
)
# Pick a search-result row that is an ACTUAL chat entry, not a section header.
# Real chat rows are role="gridcell" with tabindex="0".
S_CONTACT_RESULT = (
    "(()=>{const needle=" + json.dumps(CONTACT.lower()) + ";"
    "const grid=document.querySelector('div[role=\"grid\"][aria-label*=\"Search results\"]')"
    "         || document.querySelector('#pane-side div[role=\"grid\"]');"
    "if(!grid)return null;"
    # gridcells are real chat rows; section headers don't have tabindex
    "const rows=[...grid.querySelectorAll('div[role=\"gridcell\"][tabindex=\"0\"], div[role=\"listitem\"]')];"
    "for(const r of rows){"
    "  const tx=(r.innerText||'').toLowerCase();"
    "  if(tx.includes(needle)) return r;"
    "}"
    "return null;})()"
)
# After the chat opens, verify by looking for the OPEN-CHAT header (inside #main).
# Note: there are multiple <header> elements on the page (sidebar, etc.);
# only the one inside #main has the chat title.
S_CHAT_OPEN_HEADER = (
    "(()=>{const needle=" + json.dumps(CONTACT.lower()) + ".replace(/\\s*\\(you\\)\\s*/i,'').trim();"
    "const hdr=document.querySelector('#main header');"
    "if(!hdr)return null;"
    "const t=(hdr.innerText||'').toLowerCase();"
    "return t.includes(needle)?hdr:null;})()"
)
# Attach (paperclip / plus) button at the bottom of the open chat
S_ATTACH_BUTTON = (
    "document.querySelector('footer [data-testid=\"conversation-clip\"], "
    "footer [aria-label=\"Attach\"], "
    "footer button[aria-label*=\"Attach\"], "
    "footer [data-icon=\"plus-rounded\"], "
    "footer [data-icon=\"clip\"]')?.closest('button,[role=\"button\"]')"
)
# Poll menu item (appears after clicking attach)
S_POLL_MENU_ITEM = (
    "[...document.querySelectorAll('li, div[role=\"button\"], button')]"
    ".find(e=>e.offsetParent!==null && /^(create\\s*)?poll$/i.test((e.innerText||'').trim()))"
)
# Poll dialog elements
S_POLL_DIALOG = "document.querySelector('div[role=\"dialog\"]')"
S_POLL_QUESTION = (
    "(()=>{const d=" + S_POLL_DIALOG + ";if(!d)return null;"
    "return d.querySelector('div[contenteditable=\"true\"]');})()"
)
S_POLL_OPTION_INPUTS = (
    "(()=>{const d=" + S_POLL_DIALOG + ";if(!d)return [];"
    "return [...d.querySelectorAll('div[contenteditable=\"true\"]')].slice(1);})()"
)
S_POLL_SEND_BUTTON = (
    "(()=>{const d=" + S_POLL_DIALOG + ";if(!d)return null;"
    # Send is a DIV with aria-label="Send" — not a real button/role=button.
    "const cands=[...d.querySelectorAll('[aria-label=\"Send\"]')]"
    ".filter(e=>e.offsetParent!==null);"
    "if(cands.length) return cands[0];"
    # Fallback: any button-ish whose label/text matches send
    "return [...d.querySelectorAll('button, [role=\"button\"], div[aria-label]')]"
    ".find(b=>b.offsetParent!==null && /send/i.test((b.getAttribute('aria-label')||b.innerText||'')));"
    "})()"
)


S_MESSAGE_COMPOSER = (
    "(()=>{"
    # The composer is a contenteditable with aria-label starting "Type a message"
    "const cs=[...document.querySelectorAll('#main div[contenteditable=\"true\"][role=\"textbox\"]')]"
    ".filter(e=>e.offsetParent!==null);"
    "const typed=cs.find(e=>{const a=(e.getAttribute('aria-label')||'').toLowerCase();return a.startsWith('type a message');});"
    "return typed || cs[0];})()"
)
S_MESSAGE_SEND_BUTTON = (
    "document.querySelector('#main button[aria-label=\"Send\"], #main [aria-label=\"Send\"]')"
)

# Read the latest volleyball poll in the open chat and parse Yes/No vote counts.
S_LATEST_POLL_VOTES = (
    "(()=>{"
    "const main=document.querySelector('#main');"
    "if(!main) return {found:false,error:'no_main'};"
    "const scrollers=[...main.querySelectorAll("
    "'div.copyable-area [tabindex=\"-1\"], [data-testid=\"conversation-panel-body\"]'"
    ")];"
    "scrollers.forEach(s=>{s.scrollTop=s.scrollHeight;});"
    "const rows=[...main.querySelectorAll("
    "'div[data-id], [data-testid=\"msg-container\"], div.message-in, div.message-out'"
    ")];"
    "const needles=['volleyball','shall we play'];"
    "function pickCount(text,label){"
    "  const re=new RegExp('\\\\b'+label+'\\\\b[\\\\s\\\\S]{0,80}?(\\\\d+)','i');"
    "  const m=text.match(re);"
    "  return m?parseInt(m[1],10):null;"
    "}"
    "function parseVotes(msg){"
    "  const txt=(msg.innerText||'');"
    "  const lower=txt.toLowerCase();"
    "  if(!needles.some(n=>lower.includes(n))) return null;"
    "  if(!/\\bview votes\\b/i.test(txt)&&!/\\byes\\b/i.test(txt)) return null;"
    "  let yesVotes=pickCount(txt,'yes');"
    "  let noVotes=pickCount(txt,'no');"
    "  const lines=txt.split('\\n').map(l=>l.trim()).filter(Boolean);"
    "  for(let j=0;j<lines.length;j++){"
    "    const yesInline=lines[j].match(/^yes\\b\\s*(\\d+)?/i);"
    "    if(yesInline&&yesInline[1]) yesVotes=parseInt(yesInline[1],10);"
    "  else if(/^yes$/i.test(lines[j])){"
    "      for(let k=j+1;k<Math.min(j+6,lines.length);k++){"
    "        const m=lines[k].match(/^(\\d+)$/);"
    "        if(m){yesVotes=parseInt(m[1],10);break;}"
    "      }"
    "    }"
    "    const noInline=lines[j].match(/^no\\b\\s*(\\d+)?/i);"
    "    if(noInline&&noInline[1]) noVotes=parseInt(noInline[1],10);"
    "  else if(/^no$/i.test(lines[j])){"
    "      for(let k=j+1;k<Math.min(j+6,lines.length);k++){"
    "        const m=lines[k].match(/^(\\d+)$/);"
    "        if(m){noVotes=parseInt(m[1],10);break;}"
    "      }"
    "    }"
    "  }"
    "  const pollRoot=msg.querySelector('[data-testid*=\"poll\"], [role=\"list\"]')||msg;"
    "  const optionRows=[...pollRoot.querySelectorAll("
    "'div[role=\"button\"], li, label, span'"
    ")];"
    "  for(const row of optionRows){"
    "    const rowTxt=(row.innerText||'').trim();"
    "    if(!rowTxt) continue;"
    "    const nums=[...rowTxt.matchAll(/(\\d+)/g)].map(m=>parseInt(m[1],10));"
    "    if(/^yes\\b/i.test(rowTxt)&&nums.length) yesVotes=nums[nums.length-1];"
    "    if(/^no\\b/i.test(rowTxt)&&nums.length) noVotes=nums[nums.length-1];"
    "  }"
    "  const els=[...msg.querySelectorAll('[aria-label],[role=\"button\"],button,span')]"
    "  .filter(e=>e.offsetParent!==null);"
    "  for(const el of els){"
    "    const label=(el.getAttribute('aria-label')||el.innerText||'').trim();"
    "    const vm=label.match(/(\\d+)\\s*(?:vote|votes)/i)||label.match(/^(\\d+)$/);"
    "    if(!vm) continue;"
    "    const v=parseInt(vm[1],10);"
    "    if(/\\byes\\b/i.test(label)) yesVotes=v;"
    "    else if(/\\bno\\b/i.test(label)) noVotes=v;"
    "  }"
    "  if(yesVotes===null&&noVotes===null){"
    "    const nums=[...txt.matchAll(/(\\d+)\\s*(?:vote|votes)?/gi)].map(m=>parseInt(m[1],10));"
    "    if(nums.length>=2){yesVotes=nums[0];noVotes=nums[1];}"
    "  }"
    "  if(yesVotes===null&&noVotes===null) return null;"
    "  return {"
    "    found:true,"
    "    yesVotes:yesVotes??0,"
    "    noVotes:noVotes??0,"
    "    preview:txt.slice(0,240).replace(/\\s+/g,' ').trim()"
    "  };"
    "}"
    "for(let i=rows.length-1;i>=0;i--){"
    "  const parsed=parseVotes(rows[i]);"
    "  if(parsed) return parsed;"
    "}"
    "return {found:false,error:'no_poll_found'};"
    "})()"
)


def scroll_chat_to_bottom(tab: Tab) -> None:
    try:
        tab.eval(
            "const main=document.querySelector('#main');"
            "if(!main) return false;"
            "const scrollers=[...main.querySelectorAll("
            "'div.copyable-area [tabindex=\"-1\"], [data-testid=\"conversation-panel-body\"]'"
            ")];"
            "scrollers.forEach(s=>{s.scrollTop=s.scrollHeight;});"
            "return true;"
        )
        time.sleep(1.0)
    except Exception as exc:
        log(f"scroll chat: {exc}")


def read_latest_poll_votes(tab: Tab) -> dict:
    """Return {found, yesVotes, noVotes, preview, error?} from the open chat."""
    scroll_chat_to_bottom(tab)
    for attempt in range(3):
        try:
            data = tab.eval(f"return ({S_LATEST_POLL_VOTES});", timeout=20)
            if isinstance(data, dict):
                return data
        except Exception as exc:
            log(f"poll read attempt {attempt + 1}: {exc}")
        time.sleep(1.0)
    return {"found": False, "error": "read_failed"}


def _finish_turnout(detail: str) -> int:
    mark_turnout_success("turnout", detail=detail, message_sent=True)
    log(f"turnout complete: message sent ({detail})")
    return 0


def run_turnout_check(tab: Tab) -> int:
    """Friday turnout check: weather for today's game, then poll Yes count.

    Sends the appropriate WhatsApp message when required:
      - Rain or temperature out of range → weather cancellation message
      - Weather OK but Yes votes < MIN_PLAYERS → low-turnout cancellation
      - Weather OK and enough Yes votes → all-clear \"let's play\" message
    """
    weather_decision = "proceed"
    cancel_reason = ""
    if not SKIP_WEATHER:
        try:
            weather_decision, msg, cancel_reason = weather_check_today()
            if msg:
                for line in msg.splitlines():
                    log(line)
        except Exception as exc:
            log(f"weather: check failed ({exc}) — proceeding with turnout read")
            weather_decision = "proceed"

    if weather_decision == "cancel":
        cancel_msg = CANCEL_MSG if cancel_reason == "rain" else TEMP_CANCEL_MSG
        log("=" * 60)
        if cancel_reason == "temp":
            log(
                "TEMP OUT OF RANGE — sending weather cancellation message "
                "(skipping turnout poll read)"
            )
        else:
            log(
                "RAINY DAY — sending weather cancellation message "
                "(skipping turnout poll read)"
            )
        log("=" * 60)
        send_text_message(tab, cancel_msg)
        detail = "weather_rain" if cancel_reason == "rain" else "weather_temp"
        return _finish_turnout(detail)

    if weather_decision == "proceed":
        log("weather OK for today's game window — checking poll turnout")

    info = read_latest_poll_votes(tab)
    if not info.get("found"):
        fail(f"could not find a volleyball poll in chat: {info.get('error', 'unknown')}")

    yes_votes = int(info.get("yesVotes") or 0)
    no_votes = int(info.get("noVotes") or 0)
    preview = info.get("preview") or ""
    log(f"latest poll: Yes={yes_votes}  No={no_votes}  (need>={MIN_PLAYERS} Yes)")
    if preview:
        log(f"poll preview: {preview[:120]}...")

    if yes_votes >= MIN_PLAYERS:
        log(
            f"enough players ({yes_votes} Yes) and weather OK — "
            "sending all-clear let's-play message"
        )
        send_text_message(tab, GO_MSG)
        return _finish_turnout("go_msg")

    log(
        f"NOT ENOUGH PLAYERS ({yes_votes} Yes, need {MIN_PLAYERS}) "
        "— sending low-turnout cancellation"
    )
    send_text_message(tab, LOW_TURNOUT_MSG)
    return _finish_turnout("low_turnout")


def run_send_low_turnout_cancel(tab: Tab) -> int:
    """Send the low-turnout cancellation message without reading the poll."""
    log("sending low-turnout cancellation message (manual / forced)")
    send_text_message(tab, LOW_TURNOUT_MSG)
    return 0


def _parse_load_info(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    return {"ready": False, "reason": "bad_eval", "raw": repr(raw)[:120]}


def ensure_whatsapp_session(tab: Tab) -> None:
    """Open web.whatsapp.com, click Log in if needed, wait until chat list loads."""
    try:
        tab._call("Page.bringToFront", timeout=5)
    except Exception:
        pass

    url = tab.eval("return location.href;") or ""
    if "web.whatsapp.com" not in url:
        tab.eval("location.href='https://web.whatsapp.com/'; return true;")
        time.sleep(3.0)
        url = tab.eval("return location.href;") or ""
    log(f"on: {url}")
    log(
        f"checking WhatsApp login state "
        f"(timeout={SESSION_TIMEOUT_SEC}s, scheduled={SCHEDULED})…"
    )

    deadline = time.time() + SESSION_TIMEOUT_SEC
    login_clicked = False
    reload_attempted = False
    last_log = time.time()
    sidebar_seen = False
    while time.time() < deadline:
        state = "unknown"
        logged_in = False
        try:
            logged_in = bool(tab.eval(S_LOGGED_IN, timeout=8))
        except Exception as exc:
            log(f"login check: {exc}")
        if logged_in:
            sidebar_seen = True
            try:
                load_info = _parse_load_info(tab.eval(S_CHATS_FULLY_LOADED, timeout=10))
            except Exception as exc:
                load_info = {"ready": False, "reason": f"eval_err:{exc}"}
            if load_info.get("ready"):
                rows = load_info.get("rows", "?")
                log(f"WhatsApp chat list ready ({rows} chats visible)")
                if POST_READY_SETTLE_SEC > 0:
                    log(
                        f"waiting {POST_READY_SETTLE_SEC}s for chats/messages to finish syncing "
                        "(do not click away from Edge)…"
                    )
                    time.sleep(POST_READY_SETTLE_SEC)
                log("WhatsApp Web session ready")
                return
            reason = load_info.get("reason", "unknown")
            rows = load_info.get("rows", "?")
            if time.time() - last_log >= 5:
                secs_left = int(deadline - time.time())
                log(
                    f"sidebar visible but chats still loading "
                    f"(reason={reason!r}, rows={rows}, {secs_left}s left)"
                )
                last_log = time.time()
            time.sleep(1.5)
            continue

        try:
            state = tab.eval(S_WHATSAPP_STATE, timeout=8) or "unknown"
        except Exception as exc:
            log(f"state check: {exc}")

        if time.time() - last_log >= 5:
            secs_left = int(deadline - time.time())
            log(f"waiting for WhatsApp… state={state!r} ({secs_left}s left)")
            if state == "qr":
                log("→ Scan the QR code in the Edge window with your phone.")
            elif state == "landing":
                log("→ Click Log in / link with phone number in Edge if prompted.")
            elif state == "loading":
                log("→ WhatsApp is still loading or syncing chats.")
            elif sidebar_seen:
                log("→ Chat sidebar appeared; waiting for chat rows to populate.")
            last_log = time.time()

        if state == "loading" and not reload_attempted:
            elapsed = SESSION_TIMEOUT_SEC - int(deadline - time.time())
            if elapsed > 45:
                log("still loading — reloading WhatsApp tab once")
                try:
                    tab.eval("location.reload(); return true;")
                except Exception as exc:
                    log(f"reload failed: {exc}")
                reload_attempted = True
                time.sleep(6.0)
                continue

        if not login_clicked and state in ("landing", "unknown"):
            try:
                login_btn = tab.eval(f"return !!({S_LOGIN_BUTTON});")
                if login_btn:
                    log("not logged in — clicking Log in")
                    tab.click(S_LOGIN_BUTTON, "Log in with phone number", timeout=8)
                    login_clicked = True
                    time.sleep(2.0)
            except Exception as exc:
                log(f"login click attempt: {exc}")

        time.sleep(1.0)

    if TRACE:
        tab._dump_dom_summary("WhatsApp login timeout")
    try:
        state = tab.eval(S_WHATSAPP_STATE)
        log(f"final WhatsApp state: {state!r}")
        if state == "ready":
            log(
                "strict chat-load check timed out but WhatsApp looks ready — continuing"
            )
            if POST_READY_SETTLE_SEC > 0:
                time.sleep(POST_READY_SETTLE_SEC)
            log("WhatsApp Web session ready")
            return
    except Exception:
        pass
    fail(
        f"WhatsApp Web did not finish loading within {SESSION_TIMEOUT_SEC}s. "
        "Open Edge, finish login at web.whatsapp.com (scan QR), wait for chats to load, then re-run."
    )


def open_contact_chat(tab):
    """Run the search → click → header-verify flow. Returns when chat is open."""
    try:
        tab._call("Page.bringToFront", timeout=5)
    except Exception:
        pass
    if PRE_SEARCH_SETTLE_SEC > 0:
        log(f"pausing {PRE_SEARCH_SETTLE_SEC}s before opening chat search…")
        time.sleep(PRE_SEARCH_SETTLE_SEC)
    # Close any open in-chat search panel from prior runs.
    try:
        tab.eval(
            "const closeBtns=[...document.querySelectorAll('button[aria-label=\"Close\"]')]"
            ".filter(b=>{const r=b.getBoundingClientRect();return r.x>1000&&b.offsetParent!==null;});"
            "if(closeBtns.length){closeBtns[0].click();return true;}return false;"
        )
        time.sleep(0.3)
    except Exception:
        pass

    # Try to locate the search field. If we can't, dump every input-like
    # element on the page so the next selector fix is one edit away.
    try:
        tab.click(S_SEARCH_BUTTON, "Search button (chat list)")
    except Exception as exc:
        log(f"could not locate chat-list search field: {exc}")
        try:
            diag = tab.eval(_SEARCH_DIAG_EXPR)
            log("--- DIAGNOSTIC: all visible input-like elements ---")
            log(diag or "(none found — is WhatsApp Web actually loaded?)")
            log("Update _SEARCH_INPUT_EXPR in whatsapp_poll.py using the dump above.")
        except Exception as exc2:
            log(f"diagnostic dump failed: {exc2}")
        raise
    time.sleep(0.6)
    tab.wait(f"!!({S_SEARCH_BOX})", "search input field", timeout=10)
    tab.focus(S_SEARCH_BOX, "search box")
    tab.eval(
        "const el=document.activeElement;"
        "if(el && 'value' in el){"
        "  const proto=Object.getPrototypeOf(el);"
        "  const desc=Object.getOwnPropertyDescriptor(proto,'value');"
        "  if(desc&&desc.set){desc.set.call(el,'');"
        "    el.dispatchEvent(new Event('input',{bubbles:true}));}"
        "} else if(el){el.innerText='';el.dispatchEvent(new Event('input',{bubbles:true}));}"
        "return true;"
    )
    time.sleep(0.2)
    tab.insert_text(CONTACT)
    time.sleep(3.0 if SCHEDULED else 2.0)
    actual = tab.eval(
        "const el=document.activeElement;"
        "return el ? (el.value!==undefined?el.value:el.innerText||el.textContent||'') : '';"
    )
    log(f"search box value after typing: {actual!r}")
    tab.wait(f"!!({S_CONTACT_RESULT})", f"search result for {CONTACT!r}", timeout=25 if SCHEDULED else 15)
    tab.click(S_CONTACT_RESULT, f"open chat: {CONTACT}")
    time.sleep(1.0 if SCHEDULED else 0.6)
    tab.wait(f"!!({S_CHAT_OPEN_HEADER})", f"chat header for {CONTACT!r}", timeout=40 if SCHEDULED else 25)


def send_text_message(tab, text: str) -> None:
    """Type `text` into the open chat's composer and click Send."""
    tab.wait(f"!!({S_MESSAGE_COMPOSER})", "message composer", timeout=15)
    tab.focus(S_MESSAGE_COMPOSER, "message composer")
    # Clear any draft using execCommand (the contenteditable-correct way)
    tab.eval(
        "const el=document.activeElement;"
        "if(el){document.execCommand('selectAll', false, null);"
        "document.execCommand('delete', false, null);"
        "el.dispatchEvent(new Event('input',{bubbles:true}));}"
        "return true;"
    )
    time.sleep(0.2)
    tab.insert_text(text)
    time.sleep(0.6)
    if not SEND:
        log(f"DRY-RUN: composer filled with {text!r} — not clicking Send.")
        return
    tab.wait(f"!!({S_MESSAGE_SEND_BUTTON})", "message Send button", timeout=10)
    tab.click(S_MESSAGE_SEND_BUTTON, "Send message")
    # Confirm sent: composer should be cleared
    tab.wait(
        "(()=>{const el=" + S_MESSAGE_COMPOSER + ";return el && (el.innerText||'').trim()==='';})()",
        "composer cleared (message sent)",
        timeout=10,
    )
    log("✓ message sent")


def send_poll(tab) -> None:
    """Open Attach → Poll, fill question + Yes/No, and (optionally) Send."""
    # Defensive: clear any draft text the chat composer may still hold
    # (e.g. from a previous dry-run that left text behind).
    try:
        tab.eval(
            "const el=" + S_MESSAGE_COMPOSER + ";"
            "if(el){el.focus();document.execCommand('selectAll', false, null);"
            "document.execCommand('delete', false, null);"
            "el.dispatchEvent(new Event('input',{bubbles:true}));}"
            "return true;"
        )
    except Exception:
        pass

    tab.click(S_ATTACH_BUTTON, "attach (paperclip)")
    time.sleep(0.6)
    tab.wait(f"!!({S_POLL_MENU_ITEM})", "Poll menu item", timeout=10)
    tab.click(S_POLL_MENU_ITEM, "Poll")

    tab.wait(f"!!({S_POLL_DIALOG})", "poll dialog", timeout=10)

    # Clear question field, then type
    tab.focus(S_POLL_QUESTION, "poll question field")
    tab.eval(
        "const el=document.activeElement;"
        "if(el){document.execCommand('selectAll', false, null);"
        "document.execCommand('delete', false, null);"
        "el.dispatchEvent(new Event('input',{bubbles:true}));}"
        "return true;"
    )
    time.sleep(0.2)
    tab.insert_text(POLL_TITLE)

    opt_count = tab.eval(f"return ({S_POLL_OPTION_INPUTS}).length;") or 0
    log(f"poll dialog shows {opt_count} option fields")
    if opt_count < len(POLL_OPTIONS):
        log(f"WARN: dialog has only {opt_count} option slots; expected {len(POLL_OPTIONS)}.")

    for i, opt_text in enumerate(POLL_OPTIONS):
        sel = f"({S_POLL_OPTION_INPUTS})[{i}]"
        tab.focus(sel, f"option {i+1} field")
        tab.insert_text(opt_text)
        time.sleep(0.3)

    time.sleep(0.6)
    if not SEND:
        log("DRY-RUN: not clicking Send. Re-run with SEND=1 to actually send the poll.")
        return

    tab.wait(f"!!({S_POLL_SEND_BUTTON})", "poll Send button", timeout=10)
    tab.click(S_POLL_SEND_BUTTON, "Send poll")
    tab.wait("!document.querySelector('div[role=\"dialog\"]')",
             "poll dialog closed (poll sent)", timeout=15)
    log("✓ poll sent")


def main() -> int:
    log(f"contact={CONTACT!r}  send={SEND}  trace={TRACE}  action={ACTION!r}")

    if ACTION in ("check_turnout", "send_low_turnout_cancel"):
        try:
            version = json.loads(_http("GET", "/json/version", timeout=3))
            browser = version.get("Browser", "Chromium")
            log(f"CDP connected: {browser}")
        except Exception as exc:
            fail(
                f"Browser CDP unreachable at {CDP_URL}: {exc}\n"
                "Run start_edge_cdp.bat first (or start_chrome_cdp.bat)."
            )

        tab_info = find_or_open_whatsapp()
        tab = Tab(tab_info["webSocketDebuggerUrl"])
        try:
            ensure_whatsapp_session(tab)
            open_contact_chat(tab)
            if ACTION == "check_turnout":
                return run_turnout_check(tab)
            return run_send_low_turnout_cancel(tab)
        finally:
            tab.close()

    weather_decision = "proceed"
    cancel_reason = ""
    if SKIP_WEATHER:
        log("weather: SKIP_WEATHER=1 → skipping weather check")
    else:
        try:
            weather_decision, msg, cancel_reason = weather_check_tomorrow()
        except Exception as exc:
            log(f"weather: check failed ({exc}) — proceeding without it")
            weather_decision = "proceed"
            msg = ""
        if msg:
            for line in msg.splitlines():
                log(line)

    if weather_decision == "skip":
        return 0

    cancelled = weather_decision == "cancel"
    cancel_msg = CANCEL_MSG if cancel_reason == "rain" else TEMP_CANCEL_MSG

    if cancelled:
        log("=" * 60)
        if cancel_reason == "temp":
            log("TEMP OUT OF RANGE — will send cancellation message instead of poll.")
        else:
            log("RAINY DAY — will send cancellation message instead of poll.")
        log("=" * 60)

    # CDP sanity (Edge or Chrome — any Chromium browser on port 9222)
    try:
        version = json.loads(_http("GET", "/json/version", timeout=3))
        browser = version.get("Browser", "Chromium")
        log(f"CDP connected: {browser}")
    except Exception as exc:
        fail(
            f"Browser CDP unreachable at {CDP_URL}: {exc}\n"
            "Run start_edge_cdp.bat first (or start_chrome_cdp.bat)."
        )

    tab_info = find_or_open_whatsapp()
    tab = Tab(tab_info["webSocketDebuggerUrl"])
    try:
        ensure_whatsapp_session(tab)
        open_contact_chat(tab)

        if cancelled:
            send_text_message(tab, cancel_msg)
        else:
            send_poll(tab)

        return 0
    finally:
        tab.close()

if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        log(f"unexpected error: {exc!r}")
        sys.exit(2)
