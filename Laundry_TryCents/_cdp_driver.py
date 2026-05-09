#!/usr/bin/env python3
"""CDP-only laundry order driver.

Opens a new tab pinned by ID, drives it via WebSocket Runtime.evaluate.
No Selenium, no Playwright, no browser-use. Just stdlib + websocket-client.

Selectors verified live by walking through the flow once with the user.
"""
import json
import os
import sys
import time
import urllib.request
import websocket  # provided by browser-use venv

CDP_URL = os.environ.get("CDP_URL", "http://localhost:9222")
ORDER_URL = os.environ.get("ORDER_URL", "https://app.trycents.com/new-order/N3c4/home")
TIME_SLOT = os.environ.get("TIME_SLOT", "04:30PM-06:00PM")


def log(msg: str) -> None:
    print(f"[laundry] {msg}", flush=True)


def fail(msg: str) -> None:
    log(f"FAIL: {msg}")
    sys.exit(1)


def open_tab(url: str) -> dict:
    data = urllib.request.urlopen(
        urllib.request.Request(f"{CDP_URL}/json/new?{url}", method="PUT"),
        timeout=10,
    ).read()
    return json.loads(data)


def ws_eval(ws_url: str, expr: str, timeout: float = 10) -> object:
    ws = websocket.create_connection(ws_url, timeout=timeout)
    try:
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": f"(()=>{{{expr}}})()",
                "returnByValue": True,
                "awaitPromise": False,
            },
        }))
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == 1:
                if "error" in r:
                    raise RuntimeError(r["error"])
                res = r.get("result", {}).get("result", {})
                if res.get("subtype") == "error":
                    raise RuntimeError(res.get("description", "JS error"))
                return res.get("value")
    finally:
        ws.close()


class Tab:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url

    def eval(self, expr: str, timeout: float = 10) -> object:
        return ws_eval(self.ws_url, expr, timeout)

    def wait(self, expr: str, label: str, timeout: float = 20, poll: float = 0.5) -> object:
        """Eval expr until it returns truthy. Returns the truthy value."""
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
        fail(f"timed out waiting for: {label} (last={last!r})")
        return None  # unreachable

    def click(self, selector_js: str, label: str, timeout: float = 15) -> None:
        """selector_js must be a JS expression that returns the element to click,
        or null/undefined if not yet present."""
        expr = (
            f"const el=({selector_js});"
            "if(!el) return false;"
            "el.scrollIntoView({block:'center'});"
            "el.click();"
            "return true;"
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.eval(expr):
                    log(f"clicked: {label}")
                    return
            except Exception as exc:
                log(f"click attempt err on '{label}': {exc}")
            time.sleep(0.5)
        fail(f"could not click: {label}")

    def url(self) -> str:
        return self.eval("return location.href;")


def main() -> int:
    # 1. Open new tab pinned to the order URL
    log(f"opening new tab: {ORDER_URL}")
    info = open_tab(ORDER_URL)
    tab = Tab(info["webSocketDebuggerUrl"])
    log(f"tab id: {info['id'][:8]}")

    # 2. Wait for service list to render
    tab.wait("[...document.querySelectorAll('div[role=\"button\"][class*=\"_service_\"]')].some(d=>(d.innerText||'').includes('Wash and Fold'))",
             "Wash and Fold service tile", timeout=25)

    # Step 1 — click Wash and Fold service tile
    tab.click(
        "[...document.querySelectorAll('div[role=\"button\"][class*=\"_service_\"]')]"
        ".find(d=>(d.innerText||'').includes('Wash and Fold'))",
        "Wash and Fold tile",
    )

    # Step 2 — wait for detergent drawer + check Gain Detergent
    tab.wait("!!document.querySelector('.MuiDrawer-paper')", "drawer open", timeout=15)
    tab.wait(
        "[...document.querySelectorAll('.MuiDrawer-paper div[role=\"button\"][class*=\"_addon_\"]')]"
        ".some(d=>(d.innerText||'').toLowerCase().startsWith('gain'))",
        "Gain Detergent option", timeout=15,
    )
    tab.click(
        "[...document.querySelectorAll('.MuiDrawer-paper div[role=\"button\"][class*=\"_addon_\"]')]"
        ".find(d=>(d.innerText||'').toLowerCase().startsWith('gain'))",
        "Gain Detergent",
    )

    # Step 3 — Add to Order button (drawer)
    tab.click(
        "[...document.querySelectorAll('.MuiDrawer-paper button')]"
        ".find(b=>(b.innerText||'').trim()==='Add to Order')",
        "Add to Order",
    )

    # Step 4 — wait for drawer to close + cart Next button (sticky)
    tab.wait("!document.querySelector('.MuiDrawer-paper')", "drawer closed", timeout=10)
    tab.wait("!!document.querySelector('div[class*=\"_submitContainer_\"] button')",
             "cart Next button", timeout=10)
    tab.click(
        "document.querySelector('div[class*=\"_submitContainer_\"] button')",
        "cart Next",
    )

    # Step 5 — Your Basket page → Next
    tab.wait("location.href.includes('/basket')", "basket page url", timeout=15)
    tab.wait("!!document.querySelector('aside[class*=\"_nextButtonWrapper_\"] button')",
             "basket Next button", timeout=10)
    tab.click(
        "document.querySelector('aside[class*=\"_nextButtonWrapper_\"] button')",
        "basket Next",
    )

    # Step 6 — Order Summary (/checkout) → click Pickup Details card
    tab.wait("location.href.includes('/checkout')", "checkout page url", timeout=20)
    tab.wait(
        "[...document.querySelectorAll('div[role=\"button\"][class*=\"_transportationContent_\"]')]"
        ".some(d=>(d.innerText||'').includes('Pickup Details'))",
        "Pickup Details card", timeout=15,
    )
    tab.click(
        "[...document.querySelectorAll('div[role=\"button\"][class*=\"_transportationContent_\"]')]"
        ".find(d=>(d.innerText||'').includes('Pickup Details'))",
        "Pickup Details card",
    )

    # Step 7 — Schedule pickup → advance days until we find the target slot
    tab.wait("location.href.includes('/schedule/pickup')", "schedule/pickup url", timeout=15)

    slot_js = (
        "[...document.querySelectorAll('div.time-box[role=\"button\"]')]"
        f".find(d=>{{const h=d.querySelector('h6.time');return h && h.innerText.trim()==='{TIME_SLOT}';}})"
    )

    def _slots_visible():
        return tab.eval(
            "return [...document.querySelectorAll('h6.time')]"
            ".filter(h=>h.offsetParent!==null).map(h=>h.innerText.trim());"
        ) or []

    def _current_day():
        return tab.eval(
            "const e=document.querySelector('.date-title')||document.querySelector('h4.day');"
            "return e?e.innerText.replace(/\\n/g,' '):'';"
        ) or ""

    MAX_ADVANCES = 7
    for attempt in range(MAX_ADVANCES + 1):
        day = _current_day()
        slots = _slots_visible()
        log(f"day '{day}' has slots: {slots}")
        if tab.eval(f"return !!({slot_js});"):
            log(f"target slot found on '{day}'")
            break
        if attempt == MAX_ADVANCES:
            fail(f"slot {TIME_SLOT} not found within {MAX_ADVANCES} days "
                 f"(last day checked: '{day}', last slots: {slots})")
        # advance one day
        tab.wait("!!document.querySelector('[role=\"button\"][aria-label=\"Next day\"]')",
                 "Next-day chevron", timeout=10)
        tab.click(
            "document.querySelector('[role=\"button\"][aria-label=\"Next day\"]')",
            f"Next day chevron (attempt {attempt+1})",
        )
        time.sleep(1.5)  # let slots re-render

    # Step 8 — click the target slot
    tab.click(slot_js, f"time slot {TIME_SLOT}")

    # Step 9 — Set pickup time button
    tab.wait(
        "[...document.querySelectorAll('button')].some(b=>/^set\\s*pickup/i.test((b.innerText||'').trim()))",
        "Set pickup time button", timeout=10,
    )
    tab.click(
        "[...document.querySelectorAll('button')]"
        ".find(b=>/^set\\s*pickup/i.test((b.innerText||'').trim()))",
        "Set pickup time",
    )

    # Step 10 — back on /checkout — STOP. User takes over.
    tab.wait("location.href.includes('/checkout')", "back on checkout", timeout=15)
    log("✓ pickup time set — Order Summary loaded. STOPPED here for user review.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        log(f"unexpected error: {exc!r}")
        sys.exit(2)
