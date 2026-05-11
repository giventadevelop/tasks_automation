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
    "Friday 6:00 PM at Lake Hiawatha Park — https://g.co/kgs/FrFYPm8\n"
    "Hosted by Parsippany Rescue & Recovery Unit.\n"
    "Please confirm by noon Friday."
)
POLL_TITLE = os.environ.get("POLL_TITLE", DEFAULT_TITLE)
POLL_OPTIONS = ["Yes", "No"]
SEND = os.environ.get("SEND", "") == "1"
TRACE = os.environ.get("TRACE", "") == "1"


# Default contact (used when env var is unset OR empty).
DEFAULT_CONTACT = "Gain Joseph"
CONTACT = os.environ.get("CONTACT", "").strip() or DEFAULT_CONTACT


def log(msg: str) -> None:
    print(f"[wapoll] {msg}", flush=True)


def fail(msg: str) -> None:
    log(f"FAIL: {msg}")
    sys.exit(1)


def _http(method: str, path: str, timeout: float = 10) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(f"{CDP_URL}{path}", method=method), timeout=timeout
    ).read()


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

        Three strategies, in order:
        1. Input.insertText (works for contenteditable + most inputs)
        2. Direct value setter + input event (works for stubborn React inputs)
        3. Character-by-character Input.dispatchKeyEvent (last resort)
        """
        # Strategy 1 — insertText
        try:
            self._call("Input.insertText", {"text": text}, timeout=10)
        except Exception as exc:
            log(f"insertText failed: {exc}")

        # Verify it took
        try:
            ok = self.eval(
                "const el=document.activeElement;"
                "if(!el)return false;"
                "const v=el.value!==undefined?el.value:el.innerText||el.textContent||'';"
                f"return v.includes({json.dumps(text)});"
            )
        except Exception:
            ok = False
        if ok:
            return

        # Strategy 2 — direct value setter for inputs (React-safe)
        try:
            self.eval(
                "const el=document.activeElement;"
                "if(!el)return false;"
                "if('value' in el){"
                "  const proto=Object.getPrototypeOf(el);"
                "  const desc=Object.getOwnPropertyDescriptor(proto,'value');"
                "  if(desc&&desc.set){"
                f"   desc.set.call(el, {json.dumps(text)});"
                "    el.dispatchEvent(new Event('input',{bubbles:true}));"
                "    el.dispatchEvent(new Event('change',{bubbles:true}));"
                "    return true;"
                "  }"
                "}"
                "return false;"
            )
        except Exception as exc:
            log(f"value-set fallback failed: {exc}")

        # Verify again
        try:
            ok = self.eval(
                "const el=document.activeElement;"
                "if(!el)return false;"
                "const v=el.value!==undefined?el.value:el.innerText||el.textContent||'';"
                f"return v.includes({json.dumps(text)});"
            )
        except Exception:
            ok = False
        if ok:
            return

        # Strategy 3 — type each char as a key event
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
    "return [...d.querySelectorAll('button, [role=\"button\"]')]"
    ".find(b=>b.offsetParent!==null && /send/i.test((b.getAttribute('aria-label')||b.innerText||'')));"
    "})()"
)


def main() -> int:
    log(f"contact={CONTACT!r}  send={SEND}  trace={TRACE}")

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

        # WhatsApp Web takes a while on first load
        tab.wait(
            "!!document.querySelector('#pane-side, #side, [data-testid=\"chat-list\"]')",
            "WhatsApp Web sidebar (logged in?)",
            timeout=60,
        )

        # First, close any open in-chat search panel (right side) from prior runs.
        try:
            tab.eval(
                "const closeBtns=[...document.querySelectorAll('button[aria-label=\"Close\"]')]"
                ".filter(b=>{const r=b.getBoundingClientRect();return r.x>1000&&b.offsetParent!==null;});"
                "if(closeBtns.length){closeBtns[0].click();return true;}return false;"
            )
            time.sleep(0.3)
        except Exception:
            pass

        # Search → contact.  Click the LEFT (chat-list) Search button first to
        # reveal the input, then type.
        tab.click(S_SEARCH_BUTTON, "Search button (chat list)")
        time.sleep(0.6)
        tab.wait(f"!!({S_SEARCH_BOX})", "search input field", timeout=10)
        tab.focus(S_SEARCH_BOX, "search box")
        # Clear any stale value
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
        # Type the contact name
        tab.insert_text(CONTACT)
        time.sleep(2.0)
        # Verify the value actually landed
        actual = tab.eval(
            "const el=document.activeElement;"
            "return el ? (el.value!==undefined?el.value:el.innerText||el.textContent||'') : '';"
        )
        log(f"search box value after typing: {actual!r}")
        tab.wait(f"!!({S_CONTACT_RESULT})", f"search result for {CONTACT!r}", timeout=15)
        tab.click(S_CONTACT_RESULT, f"open chat: {CONTACT}")

        # Confirm chat opened by checking the header title contains the name.
        # Use 25s — WhatsApp can be slow to swap heavy chats.
        time.sleep(0.6)  # give the click a beat to register
        tab.wait(f"!!({S_CHAT_OPEN_HEADER})", f"chat header for {CONTACT!r}", timeout=25)

        # Open attach menu, then Poll
        tab.click(S_ATTACH_BUTTON, "attach (paperclip)")
        time.sleep(0.6)
        tab.wait(f"!!({S_POLL_MENU_ITEM})", "Poll menu item", timeout=10)
        tab.click(S_POLL_MENU_ITEM, "Poll")

        # Poll dialog
        tab.wait(f"!!({S_POLL_DIALOG})", "poll dialog", timeout=10)

        # Fill question
        tab.focus(S_POLL_QUESTION, "poll question field")
        tab.insert_text(POLL_TITLE)

        # Fill options. WhatsApp shows N empty option fields by default; we focus
        # each and insert the text. If we need more than 2, we'd Tab to add new.
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
            return 0

        # Send
        tab.wait(f"!!({S_POLL_SEND_BUTTON})", "poll Send button", timeout=10)
        tab.click(S_POLL_SEND_BUTTON, "Send poll")

        # Verify a poll bubble appeared in the chat
        tab.wait(
            "[...document.querySelectorAll('div[role=\"row\"], div[data-id]')]"
            ".some(r=>/poll/i.test((r.innerText||'')) && r.innerText.includes("
            + json.dumps(POLL_OPTIONS[0])
            + "))",
            "poll bubble visible in chat",
            timeout=15,
        )
        log("✓ poll sent and visible in thread")
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
