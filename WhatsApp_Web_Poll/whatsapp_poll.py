#!/usr/bin/env python3
"""WhatsApp Web poll automation via CDP-attached Chrome.

Strategy mirrors Laundry_TryCents/_cdp_driver.py:
  * Attaches to a Chrome already running with --remote-debugging-port=9222
  * Finds (or opens) the web.whatsapp.com tab and drives it via WebSocket
  * No Selenium / Playwright / browser-use — stdlib + websocket-client only

Safety: defaults to DRY-RUN (fills the poll but does NOT click Send).
        Set env SEND=1 to actually send.

Env vars:
  CDP_URL    default http://localhost:9222
  CONTACT    default "Joseph"
  POLL_TITLE override the question text
  SEND       "1" to actually click Send; anything else = dry run
  TRACE      "1" dumps DOM snapshots on failure (helpful first time)
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

import websocket  # provided by the browser-use venv on this machine


CDP_URL = os.environ.get("CDP_URL", "http://localhost:9222")
DEFAULT_TITLE = (
    "Shall we play Volleyball this Friday 6:00 PM at Lake Hiawatha Park — https://g.co/kgs/FrFYPm8\n"
    "📍 4 Volunteers Court, Lake Hiawatha, NJ 07034\n"
    "Next to Parsippany Rescue & Recovery Unit.\n"
    "Please confirm by noon Friday."
)
DEFAULT_CANCEL_MSG = (
    "🌧️ Rainy day — meeting cancelled this Friday. We'll regroup next week."
)
POLL_TITLE = os.environ.get("POLL_TITLE", DEFAULT_TITLE)
CANCEL_MSG = os.environ.get("CANCEL_MSG", DEFAULT_CANCEL_MSG)
POLL_OPTIONS = ["Yes", "No"]
SEND = os.environ.get("SEND", "") == "1"
TRACE = os.environ.get("TRACE", "") == "1"


# Default contact (used when env var is unset OR empty).
DEFAULT_CONTACT = "Gain Joseph"
CONTACT = os.environ.get("CONTACT", "").strip() or DEFAULT_CONTACT


# ---- Weather pre-check ----------------------------------------------------
# Location: Lake Hiawatha Park, NJ (≈4 Volunteers Court, Lake Hiawatha 07034)
# Coords are hardcoded (zip 07034 → ~40.881, -74.387). Adjust if needed.
WEATHER_LAT = float(os.environ.get("WEATHER_LAT", "40.881"))
WEATHER_LON = float(os.environ.get("WEATHER_LON", "-74.387"))
# Window we care about (tomorrow, local time): 4 PM – 8:30 PM
WEATHER_WINDOW_START_HOUR = int(os.environ.get("WEATHER_START_HOUR", "16"))
WEATHER_WINDOW_END_HOUR = int(os.environ.get("WEATHER_END_HOUR", "20"))  # rounded up: covers hour 19→20 (8 PM)
# Rain decision thresholds
RAIN_KEYWORDS = ("rain", "shower", "thunderstorm", "storm", "drizzle")
RAIN_POP_THRESHOLD = int(os.environ.get("RAIN_POP_THRESHOLD", "50"))  # %
# Skip the weather pre-check entirely (e.g. for indoor events / debugging)
SKIP_WEATHER = os.environ.get("SKIP_WEATHER", "") == "1"


def log(msg: str) -> None:
    print(f"[wapoll] {msg}", flush=True)


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


def weather_check_tomorrow() -> tuple[bool, str]:
    """Return (is_rainy, human_message).

    is_rainy=True means: in tomorrow's window 16:00–20:00 local, at least one
    hour has either (a) probability-of-precipitation >= RAIN_POP_THRESHOLD or
    (b) a shortForecast mentioning rain/showers/storms.
    """
    import datetime as _dt

    log(f"weather: fetching forecast for ({WEATHER_LAT},{WEATHER_LON})")
    points = _nws_get(f"https://api.weather.gov/points/{WEATHER_LAT},{WEATHER_LON}")
    forecast_url = points["properties"]["forecastHourly"]
    forecast = _nws_get(forecast_url)
    periods = forecast["properties"]["periods"]

    # NWS startTime is ISO-8601 with timezone offset → use it directly.
    tomorrow = (_dt.datetime.now().astimezone() + _dt.timedelta(days=1)).date()

    relevant = []
    for p in periods:
        st = _dt.datetime.fromisoformat(p["startTime"])
        if st.date() != tomorrow:
            continue
        if not (WEATHER_WINDOW_START_HOUR <= st.hour < WEATHER_WINDOW_END_HOUR):
            continue
        pop = (p.get("probabilityOfPrecipitation") or {}).get("value") or 0
        fc = p.get("shortForecast", "")
        rainy = pop >= RAIN_POP_THRESHOLD or any(k in fc.lower() for k in RAIN_KEYWORDS)
        relevant.append({
            "hour": st.strftime("%I:%M %p").lstrip("0"),
            "pop": pop,
            "forecast": fc,
            "rainy": rainy,
        })

    if not relevant:
        # NWS sometimes only has ~7 days; if we ran very late at night, tomorrow
        # may have rolled over. Treat as non-rainy but warn.
        return False, "weather: no forecast data for tomorrow's window — proceeding"

    rainy_hours = [r for r in relevant if r["rainy"]]
    lines = [f"  {r['hour']}: {r['pop']}% — {r['forecast']}" for r in relevant]
    summary = (
        f"weather check for tomorrow {tomorrow.isoformat()} "
        f"{WEATHER_WINDOW_START_HOUR:02d}:00–{WEATHER_WINDOW_END_HOUR:02d}:00 local:\n"
        + "\n".join(lines)
    )
    if rainy_hours:
        return True, summary + (
            f"\n→ RAIN expected ({len(rainy_hours)} of {len(relevant)} hours flagged). "
            "Meeting will be cancelled."
        )
    return False, summary + "\n→ no rain expected — clear to send poll."


def list_tabs() -> list:
    return [t for t in json.loads(_http("GET", "/json/list")) if t.get("type") == "page"]


def open_tab(url: str) -> dict:
    return json.loads(_http("PUT", f"/json/new?{url}"))


def find_or_open_whatsapp() -> dict:
    for t in list_tabs():
        if "web.whatsapp.com" in t.get("url", ""):
            log(f"found existing WhatsApp tab {t['id'][:8]}  {t['url']}")
            return t
    log("no WhatsApp tab — opening new one")
    return open_tab("https://web.whatsapp.com/")


class Tab:
    """Thin wrapper around CDP Runtime.evaluate + Input.* on one tab."""

    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self._id = 0

    def _call(self, method: str, params: dict | None = None, timeout: float = 15):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = json.loads(self.ws.recv())
            if r.get("id") == mid:
                if "error" in r:
                    raise RuntimeError(r["error"])
                return r.get("result")
        raise TimeoutError(f"CDP timeout: {method}")

    def eval(self, expr: str, timeout: float = 15):
        r = self._call(
            "Runtime.evaluate",
            {
                "expression": f"(()=>{{{expr}}})()",
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
# CRITICAL: there are TWO "Search" buttons in WhatsApp Web — one in the LEFT
# sidebar (chat-list search, what we want) and one in the chat HEADER (in-chat
# message search). We must pick the left one by position (x < 600).
S_SEARCH_BUTTON = (
    "(()=>{"
    "const btns=[...document.querySelectorAll('button[aria-label=\"Search\"], [role=\"button\"][aria-label=\"Search\"]')]"
    ".filter(b=>b.offsetParent!==null);"
    "return btns.find(b=>b.getBoundingClientRect().x < 600) || btns[0];"
    "})()"
)
# After clicking the LEFT search button, the chat-list search input becomes
# active.  It has aria-label="" (yes, empty) but is the left-most input[role=textbox].
S_SEARCH_BOX = (
    "(()=>{"
    "const ins=[...document.querySelectorAll('input[role=\"textbox\"], input[type=\"text\"]')]"
    ".filter(e=>e.offsetParent!==null);"
    # Prefer the LEFT-side one (chat list search)
    "const left=ins.find(e=>{const r=e.getBoundingClientRect();return r.x<400&&r.y<200&&r.width>100;});"
    "if(left) return left;"
    # Fallback: any contenteditable in top-left
    "const ce=[...document.querySelectorAll('div[contenteditable=\"true\"][role=\"textbox\"]')]"
    ".find(e=>{const r=e.getBoundingClientRect();return r.x<400&&r.y<200;});"
    "return ce || ins[0];})()"
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


def open_contact_chat(tab):
    """Run the search → click → header-verify flow. Returns when chat is open."""
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

    tab.click(S_SEARCH_BUTTON, "Search button (chat list)")
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
    time.sleep(2.0)
    actual = tab.eval(
        "const el=document.activeElement;"
        "return el ? (el.value!==undefined?el.value:el.innerText||el.textContent||'') : '';"
    )
    log(f"search box value after typing: {actual!r}")
    tab.wait(f"!!({S_CONTACT_RESULT})", f"search result for {CONTACT!r}", timeout=15)
    tab.click(S_CONTACT_RESULT, f"open chat: {CONTACT}")
    time.sleep(0.6)
    tab.wait(f"!!({S_CHAT_OPEN_HEADER})", f"chat header for {CONTACT!r}", timeout=25)


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
    log(f"contact={CONTACT!r}  send={SEND}  trace={TRACE}")

    # Weather pre-check
    cancelled = False
    if SKIP_WEATHER:
        log("weather: SKIP_WEATHER=1 → skipping weather check")
    else:
        try:
            rainy, msg = weather_check_tomorrow()
        except Exception as exc:
            log(f"weather: check failed ({exc}) — proceeding without it")
            rainy = False
            msg = ""
        if msg:
            for line in msg.splitlines():
                log(line)
        cancelled = rainy

    if cancelled:
        log("=" * 60)
        log("RAINY DAY — will send cancellation message instead of poll.")
        log("=" * 60)

    # CDP sanity
    try:
        _http("GET", "/json/version", timeout=3)
    except Exception as exc:
        fail(f"Chrome CDP unreachable at {CDP_URL}: {exc}")

    tab_info = find_or_open_whatsapp()
    tab = Tab(tab_info["webSocketDebuggerUrl"])
    try:
        url = tab.eval("return location.href;")
        log(f"on: {url}")
        tab.wait(
            "!!document.querySelector('#pane-side, #side, [data-testid=\"chat-list\"]')",
            "WhatsApp Web sidebar (logged in?)",
            timeout=60,
        )

        open_contact_chat(tab)

        if cancelled:
            send_text_message(tab, CANCEL_MSG)
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
