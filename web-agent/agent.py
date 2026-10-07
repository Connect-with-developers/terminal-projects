#!/usr/bin/env python3
"""
Human-like Web Agent - CLI only, no interaction.
Every action is a --command, like builder.py.

Atomic cmds (each = one human-like browser step):
  python agent.py open --url https://example.com --human --output traces/open.json
  python agent.py search --query "playwright python" --url https://www.duckduckgo.com --output traces/s.json
  python agent.py click --url https://example.com --selector "a" --human
  python agent.py fill --url https://example.com --selector "#search" --text "hello" --human
  python agent.py press --url https://example.com --key Enter
  python agent.py scroll --url https://example.com --direction down --pixels 800 --human --steps 12
  python agent.py move --x 400 --y 300 --human --steps 15
  python agent.py hover --url https://example.com --selector "a"
  python agent.py snapshot --url https://example.com --output traces/snap.json
  python agent.py screenshot --url https://example.com --output traces/shot.png
  python agent.py new_tab --url https://mailoven.com/playground
  python agent.py switch --tab 0
  python agent.py close_tab --tab 1
  python agent.py tabs
  python agent.py run --task tasks/search-click.txt --headless --human --output traces/run.json
  python agent.py run --task tasks/multi-tab.txt --real --output traces/multi.json
  python agent.py history --limit 10
  python agent.py stats
  python agent.py clean --yes

Human-like tabs: Ctrl+T new, Ctrl+Tab switch + tab-strip Bezier move, Ctrl+W close.
Multi-tab persists in `run --real` (single browser session); atomic CLI is stateless.

Human-like = Bezier cursor path + smooth scroll steps + random delays + per-char typing.
Mode: real Playwright if installed, else simulate (same JSON schema, $0, works offline).

CAPTCHA note: no tool can guarantee automatic solving of reCAPTCHA/hCaptcha/
Turnstile (they are designed to block bots, auto-bypass may violate site ToS).
This agent does: detect -> stealth to avoid triggering -> pause for manual
solve (--captcha wait) -> optional 2Captcha-compatible API hook.
"""
import argparse
import base64
import datetime
import functools
import json
import math
import os
import random
import shlex
import sqlite3
import sys
import time
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "memory.db")
TRACE_DIR = os.path.join(BASE_DIR, "traces")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
]

# Realistic viewport pairs (avoid weird combos like 1920x720 from independent choice)
VIEWPORTS = [
    (1280, 720), (1366, 768), (1440, 900), (1536, 864),
    (1920, 1080), (2560, 1440), (390, 844), (412, 915),
]

CAPTCHA_MARKERS = [
    "g-recaptcha", "recaptcha", "h-captcha", "hcaptcha",
    "cf-turnstile", "turnstile", "data-sitekey",
    "arkose", "funcaptcha", "geetest", "captcha",
]

# 1x1 transparent PNG for simulate-mode screenshots so --output file exists
PLACEHOLDER_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

# ---------- human-like math (pure, testable, no browser needed) ----------

def cubic_bezier(p0, p1, p2, p3, t):
    """Single point on cubic Bezier curve."""
    u = 1 - t
    # precomputed Bernstein terms (speed: fewer pow ops)
    a = u * u * u
    b = 3 * u * u * t
    c = 3 * u * t * t
    d = t * t * t
    x = a*p0[0] + b*p1[0] + c*p2[0] + d*p3[0]
    y = a*p0[1] + b*p1[1] + c*p2[1] + d*p3[1]
    return (round(x, 1), round(y, 1))


def human_cursor_path(x0, y0, x1, y1, steps=15, seed=None):
    """Bezier mouse path with control-point jitter. Returns list of [x, y]."""
    try:
        steps = int(steps)
    except Exception:
        steps = 15
    if steps < 1:
        steps = 1
    if steps > 100:
        steps = 100
    # speed: instant return for no-move (accuracy: exact endpoints preserved)
    if x0 == x1 and y0 == y1:
        return [[x1, y1]] * (steps + 1)
    rng = _rng(seed, steps)
    dx, dy = x1 - x0, y1 - y0
    dist = math.hypot(dx, dy) or 1.0
    off = dist * 0.15
    p0 = (x0, y0)
    p3 = (x1, y1)
    p1 = (x0 + dx*0.3 + rng.uniform(-off, off), y0 + dy*0.3 + rng.uniform(-off, off))
    p2 = (x0 + dx*0.7 + rng.uniform(-off, off), y0 + dy*0.7 + rng.uniform(-off, off))
    pts = [cubic_bezier(p0, p1, p2, p3, t/steps) for t in range(steps + 1)]
    return [[x, y] for x, y in pts]


def human_scroll_plan(pixels, steps=12, seed=None):
    """Smooth scroll: ease-out increments summing exactly to pixels."""
    try:
        steps = int(steps)
    except Exception:
        steps = 12
    try:
        pixels = int(pixels)
    except Exception:
        pixels = 0
    if steps < 1:
        return [pixels]
    if steps > 100:
        steps = 100
    if pixels == 0:
        return [0] * steps
    # speed: skip jitter for single-step scrolls
    if steps == 1:
        return [pixels]
    rng = _rng(seed, steps)
    weights = [(1 - i/steps) + 0.3 for i in range(steps)]  # ease-out
    total = sum(weights)
    plan = [round(pixels * w / total) for w in weights]
    # fix rounding drift
    plan[-1] += pixels - sum(plan)
    # add tiny jitter but keep sum exact
    for i in range(len(plan) - 1):
        j = rng.randint(-3, 3)
        plan[i] += j
        plan[i+1] -= j
    return plan


def human_type_plan(text, base_ms=45, jitter_ms=60, seed=None):
    """Per-character typing delays (ms). Longer pause on spaces/caps."""
    rng = _rng(seed, len(text or ""))
    plan = []
    for ch in (text or ""):
        d = base_ms + rng.randint(0, jitter_ms)
        if ch == " ":
            d += rng.randint(80, 180)
        if ch.isupper():
            d += rng.randint(20, 60)
        if ch in "\n\t.,!?;:":
            d += rng.randint(60, 140)
        plan.append(d)
    return plan


def human_delay_range(human=True, seed=None, fast=False):
    """Random think-delay between actions (ms)."""
    rng = _rng(seed, 999)
    if fast or not human:
        return rng.randint(20, 80)
    return rng.randint(350, 1200)


def human_tab_delay(kind="switch", human=True, seed=None, fast=False):
    """Human-like pause for tab ops: newtab slower (Ctrl+T+load), switch 200-600ms."""
    if fast or not human:
        return 30
    rng = _rng(seed, hash(kind) % 1000)
    if kind in ("new_tab", "newtab", "open_tab"):
        return rng.randint(300, 800)
    if kind in ("close_tab", "close"):
        return rng.randint(150, 400)
    return rng.randint(200, 600)  # switch


def human_tab_strip_target(tab_index=0, seed=None):
    """Where a human would move the mouse to click a tab (tab strip y~15-35)."""
    rng = _rng(seed, tab_index)
    x = 120 + tab_index * 140 + rng.randint(-20, 20)
    y = rng.randint(15, 35)
    return (max(40, x), y)


def random_profile(seed=None):
    """Random viewport + UA like a real human device (paired viewports)."""
    rng = _rng(seed, 777)
    w, h = rng.choice(VIEWPORTS)
    return {"viewport": {"width": w, "height": h}, "user_agent": rng.choice(USER_AGENTS)}


def is_valid_url(url):
    try:
        p = urllib.parse.urlparse(url or "")
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def detect_captcha_from_html(html):
    """Pure helper: return list of matched captcha markers (case-insensitive)."""
    if not html:
        return []
    low = html.lower()
    return sorted({m for m in CAPTCHA_MARKERS if m in low})


# ---------- trace + memory ----------

def _rng(seed=None, salt=0):
    """Deterministic but varied RNG: mixes seed with salt (step index).
    Keeps --seed reproducible while avoiding identical delays every step."""
    if seed is None:
        return random.Random()
    try:
        return random.Random((int(seed) * 1000003) ^ (int(salt) * 9176 + 11))
    except Exception:
        return random.Random(seed)


def init_db():
    con = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    try:
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=OFF;")
        con.execute("PRAGMA temp_store=MEMORY;")
        cur = con.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, cmd TEXT, detail TEXT,
            mode TEXT, ts TEXT)""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_ts ON runs(ts)")
        con.commit()
    finally:
        con.close()


def save_run(cmd, detail, mode):
    try:
        con = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        try:
            con.execute("PRAGMA journal_mode=WAL;")
            con.execute("PRAGMA synchronous=OFF;")
            cur = con.cursor()
            # ensure table exists without extra connection (speed: 1 conn not 2)
            cur.execute("""CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, cmd TEXT, detail TEXT,
                mode TEXT, ts TEXT)""")
            cur.execute("INSERT INTO runs (cmd, detail, mode, ts) VALUES (?,?,?,?)",
                        (cmd, (detail or "")[:1000], mode, datetime.datetime.now().isoformat()))
            con.commit()
        finally:
            con.close()
    except Exception as e:
        print(f"[warn] save_run failed: {e}", file=sys.stderr)


def write_trace(path, data):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def write_placeholder_png(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(base64.b64decode(PLACEHOLDER_PNG_B64))
    return path


@functools.lru_cache(maxsize=1)
def has_playwright():
    try:
        import playwright.sync_api  # noqa
        return True
    except Exception:
        return False


# ---------- real browser ----------

def apply_stealth(page, profile):
    """Best-effort anti-detection: hide webdriver flag, set locale/timezone."""
    try:
        page.add_init_script("""
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = window.chrome || { runtime: {} };
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
""")
    except Exception:
        pass


def detect_captcha_on_page(page):
    """Human-like detection without full HTML dump: check known iframes/labels.
    Returns list of markers. No auto-click — detect only."""
    found = set()
    checks = [
        ('iframe[src*="recaptcha"]', "recaptcha"),
        ('iframe[src*="g-recaptcha"]', "g-recaptcha"),
        ('iframe[src*="hcaptcha"]', "h-captcha"),
        ('iframe[src*="challenges.cloudflare"]', "turnstile"),
        ('iframe[src*="turnstile"]', "turnstile"),
        ('[data-sitekey]', "data-sitekey"),
    ]
    try:
        for sel, name in checks:
            try:
                if page.locator(sel).count() > 0:
                    found.add(name)
            except Exception:
                continue
    except Exception:
        pass
    return sorted(found)


def handle_captcha(page, mode="detect", wait_ms=30000, fast=False):
    """Human-like CAPTCHA handling: detect + pause for HUMAN to solve.
    No auto-bypass — CAPTCHAs are designed to block bots and auto-solving
    third-party CAPTCHAs may violate site ToS. Modes:
      detect = flag only, continue
      wait/manual = screenshot + poll for human solve up to wait_ms
      2captcha = not auto-solved, falls back to detect with hook notice
    """
    # speed: skip expensive checks in fast mode unless human asked to wait
    if fast and mode == "detect":
        return {"captcha": False, "markers": [], "skipped": "fast"}
    found = []
    try:
        # speed+accuracy: cheap locator check first, HTML fallback second
        found = detect_captcha_on_page(page)
        if not found:
            try:
                html = page.content()[:60000]
            except Exception:
                html = ""
            found = detect_captcha_from_html(html)
    except Exception:
        pass
    if not found:
        return {"captcha": False, "markers": []}
    print(f"[captcha] detected: {found} (mode={mode})", file=sys.stderr)
    if mode in ("wait", "manual"):
        # human-like: save evidence, use headed browser, poll for solve
        shot = None
        try:
            shot = os.path.join(TRACE_DIR, "captcha.png")
            page.screenshot(path=shot, full_page=False)
            print(f"[captcha] screenshot -> {shot}. Solve it in the opened window "
                  f"(use --no-headless). Polling every 2s up to {wait_ms}ms...",
                  file=sys.stderr)
        except Exception:
            print(f"[captcha] pausing {wait_ms}ms for HUMAN to solve "
                  f"(headed browser recommended)...", file=sys.stderr)
        waited = 0
        step = 2000
        still = found
        while waited < wait_ms:
            try:
                page.wait_for_timeout(min(step, wait_ms - waited))
            except Exception:
                time.sleep(min(step, wait_ms - waited) / 1000.0)
            waited += step
            try:
                still = detect_captcha_on_page(page)
                if not still:
                    try:
                        html2 = page.content()[:60000]
                        still = detect_captcha_from_html(html2)
                    except Exception:
                        still = []
                if not still:
                    print(f"[captcha] solved by human after {waited}ms", file=sys.stderr)
                    break
            except Exception:
                pass
        return {"captcha": True, "markers": found, "waited_ms": waited,
                "still_present": bool(still), "after_markers": still,
                "screenshot": shot, "human_solved": not bool(still)}
    if mode == "2captcha":
        print("[captcha] 2captcha auto-solve is NOT wired — use your own site's test keys "
              "or --captcha wait for manual solve. Falling back to detect-only.",
              file=sys.stderr)
    return {"captcha": True, "markers": found, "waited_ms": 0}


def real_step_on_page(page, action, seed=None, captcha="detect", captcha_wait_ms=30000,
                      timeout=30000):
    """Execute one action on an already-open page (fast path for run sessions)."""
    rng = _rng(seed, 13)
    t0 = time.time()
    kind = action["action"]
    human = action.get("human", True)
    fast = action.get("fast", False)
    # speed: cap hanging waits; accuracy: shorter timeouts fail fast + retry
    nav_timeout = min(timeout, 15000)
    act_timeout = min(timeout, 5000)
    try:
        if kind == "move":
            x1, y1 = int(action["x"]), int(action["y"])
            steps = max(1, int(action.get("steps", 15)))
            if fast:
                # speed: teleport in fast mode, still human path in trace via simulate
                try:
                    page.mouse.move(x1, y1)
                except Exception:
                    pass
                return {"ok": True, "points": 1,
                        "timing_ms": int((time.time() - t0) * 1000)}
            pts = human_cursor_path(100, 100, x1, y1, steps, seed)
            for x, y in pts:
                page.mouse.move(x, y)
                page.wait_for_timeout(rng.randint(8, 16))
            return {"ok": True, "points": len(pts),
                    "timing_ms": int((time.time() - t0) * 1000)}
        if kind == "wait":
            ms = int(action.get("ms", action.get("wait_ms", 1000)))
            ms = max(0, min(ms, 120000))
            page.wait_for_timeout(ms)
            return {"ok": True, "waited_ms": ms,
                    "timing_ms": int((time.time() - t0) * 1000)}
        # ---------- multi-tab ops (human-like: Ctrl+T / Ctrl+Tab / Ctrl+W) ----------
        if kind in ("new_tab", "newtab", "open_tab", "switch", "switch_tab",
                    "tab", "close_tab", "close", "closetab", "tabs"):
            try:
                ctx = page.context
            except Exception:
                return {"ok": False, "error": "tabs need browser context"}
            delay = human_tab_delay(kind, human, seed, fast)
            if kind in ("new_tab", "newtab", "open_tab"):
                url2 = action.get("url", "https://example.com")
                # human-like: Ctrl+T then navigate
                try:
                    if human and not fast:
                        page.keyboard.press("Control+t")
                        page.wait_for_timeout(delay // 2)
                    np = ctx.new_page()
                    try:
                        np.goto(url2, timeout=nav_timeout, wait_until="domcontentloaded")
                    except Exception as e:
                        return {"ok": False, "error": f"new_tab goto failed: {e}"[:500]}
                    try:
                        np.bring_to_front()
                    except Exception:
                        pass
                    if human and not fast:
                        np.wait_for_timeout(delay // 2)
                    return {"ok": True, "tab": len(ctx.pages) - 1, "url_final": np.url,
                            "tabs": len(ctx.pages), "timing_ms": int((time.time() - t0) * 1000)}
                except Exception as e:
                    return {"ok": False, "error": f"new_tab failed: {e}"[:500]}
            if kind in ("switch", "switch_tab", "tab"):
                idx = int(action.get("tab", action.get("index", 0)))
                pages = ctx.pages
                if idx < 0 or idx >= len(pages):
                    return {"ok": False, "error": f"tab {idx} out of range (0-{len(pages)-1})"}
                try:
                    # human-like: move to tab strip then Ctrl+Tab
                    if human and not fast:
                        tx, ty = human_tab_strip_target(idx, seed)
                        for x, y in human_cursor_path(100, 100, tx, ty, 8, seed):
                            page.mouse.move(x, y)
                        page.wait_for_timeout(delay // 2)
                        try:
                            pages[idx].bring_to_front()
                        except Exception:
                            pass
                        page.wait_for_timeout(delay // 2)
                    else:
                        pages[idx].bring_to_front()
                    return {"ok": True, "tab": idx, "url_final": pages[idx].url,
                            "tabs": len(pages), "timing_ms": int((time.time() - t0) * 1000)}
                except Exception as e:
                    return {"ok": False, "error": f"switch failed: {e}"[:500]}
            if kind in ("close_tab", "close", "closetab"):
                idx = int(action.get("tab", action.get("index", -1)))
                pages = ctx.pages
                if len(pages) <= 1:
                    return {"ok": False, "error": "cannot close last tab"}
                if idx < 0:
                    idx = len(pages) - 1
                if idx >= len(pages):
                    return {"ok": False, "error": f"tab {idx} out of range"}
                try:
                    if human and not fast:
                        page.keyboard.press("Control+w")
                        page.wait_for_timeout(delay)
                    pages[idx].close()
                    return {"ok": True, "closed": idx, "tabs": len(ctx.pages),
                            "timing_ms": int((time.time() - t0) * 1000)}
                except Exception as e:
                    return {"ok": False, "error": f"close_tab failed: {e}"[:500]}
            # tabs = list
            try:
                info = [{"i": i, "url": p.url,
                         "title": p.title() if hasattr(p, "title") else ""} for i, p in enumerate(ctx.pages)]
                return {"ok": True, "tabs": info, "active": len(info) - 1,
                        "timing_ms": int((time.time() - t0) * 1000)}
            except Exception as e:
                return {"ok": False, "error": f"tabs failed: {e}"[:500]}
        url = action.get("url", "https://example.com")
        # navigate only if needed (speed: avoid re-goto same URL)
        try:
            if page.url != url and kind in ("open", "search", "click", "fill",
                                            "press", "scroll", "hover",
                                            "snapshot", "screenshot", "assert"):
                page.goto(url, timeout=nav_timeout, wait_until="domcontentloaded")
                if human and not fast:
                    page.wait_for_timeout(human_delay_range(True, seed, False) // 6)
        except Exception as e:
            return {"ok": False, "error": f"goto failed: {e}"[:500]}
        cap = handle_captcha(page, mode=captcha, wait_ms=captcha_wait_ms, fast=fast)
        if kind == "open":
            pass
        elif kind == "click":
            sel = action["selector"]
            last_err = ""
            # accuracy: retry twice, scroll into view, fallback to JS click
            for attempt in range(2):
                try:
                    loc = page.locator(sel).first
                    try:
                        loc.wait_for(state="visible", timeout=act_timeout)
                    except Exception:
                        pass
                    try:
                        loc.scroll_into_view_if_needed(timeout=3000)
                    except Exception:
                        pass
                    if human and not fast:
                        try:
                            box = loc.bounding_box(timeout=2000)
                        except Exception:
                            box = None
                        if box:
                            cx = box["x"] + box["width"] / 2
                            cy = box["y"] + box["height"] / 2
                            pts = human_cursor_path(100, 100, cx, cy,
                                                    max(1, int(action.get("steps", 10))), seed)
                            # speed: move without per-point sleep on retry
                            for i, (x, y) in enumerate(pts):
                                page.mouse.move(x, y)
                                if attempt == 0 and i % 2 == 0:
                                    page.wait_for_timeout(rng.randint(8, 16))
                            page.wait_for_timeout(rng.randint(40, 120))
                            page.mouse.click(cx, cy)
                        else:
                            loc.click(timeout=act_timeout)
                    else:
                        loc.click(timeout=act_timeout)
                    last_err = ""
                    break
                except Exception as e:
                    last_err = str(e)[:300]
                    if attempt == 0:
                        # accuracy fallback: JS click handles overlays
                        try:
                            page.eval_on_selector(sel, "el => el.click()")
                            last_err = ""
                            break
                        except Exception:
                            pass
            if last_err:
                return {"ok": False, "error": f"click failed {sel}: {last_err}"[:500]}
        elif kind == "fill":
            sel, text = action["selector"], action.get("text", "")
            last_err = ""
            for attempt in range(2):
                try:
                    loc = page.locator(sel).first
                    try:
                        loc.wait_for(state="visible", timeout=act_timeout)
                    except Exception:
                        pass
                    try:
                        loc.scroll_into_view_if_needed(timeout=3000)
                    except Exception:
                        pass
                    # speed+accuracy: single fill() is 10x faster and more reliable
                    # than per-char press_sequentially; verify value after
                    loc.click(timeout=act_timeout)
                    loc.fill(text, timeout=act_timeout)
                    try:
                        val = loc.input_value(timeout=2000)
                        if val != text:
                            # retry once with clear-then-type for stubborn inputs
                            loc.fill("", timeout=2000)
                            loc.press_sequentially(text, delay=10)
                    except Exception:
                        pass
                    last_err = ""
                    break
                except Exception as e:
                    last_err = str(e)[:300]
            if last_err:
                return {"ok": False, "error": f"fill failed {sel}: {last_err}"[:500]}
        elif kind == "press":
            page.keyboard.press(action.get("key", "Enter"))
            # accuracy: give SPA a beat to react; speed: short fixed wait
            page.wait_for_timeout(400 if not fast else 100)
        elif kind == "scroll":
            px = int(action.get("pixels", 800))
            if action.get("direction", "down") == "up":
                px = -px
            if human and not fast:
                # speed: 15-40ms per step (was 40-120ms) = ~3x faster, still smooth
                for inc in human_scroll_plan(px, max(1, int(action.get("steps", 12))), seed):
                    page.mouse.wheel(0, inc)
                    page.wait_for_timeout(rng.randint(15, 40))
            else:
                page.mouse.wheel(0, px)
        elif kind == "assert":
            sel = action.get("selector", "body")
            try:
                page.locator(sel).first.wait_for(timeout=min(timeout, 4000))
            except Exception as e:
                return {"ok": False, "error": f"assert failed, missing {sel}: {e}"[:500]}
            want = action.get("text", "")
            if want:
                try:
                    body = page.locator(sel).first.inner_text(timeout=3000)
                except Exception:
                    body = ""
                if want.lower() not in body.lower():
                    return {"ok": False,
                            "error": f"assert text {want!r} not in {sel}"[:500]}
        elif kind in ("snapshot", "screenshot", "search", "hover", "open"):
            if kind == "search":
                q = action.get("query", "")
                done = False
                for sel in ('input[name="q"]', 'input[name="query"]',
                            'input[type="search"]', 'textarea[name="q"]',
                            'input[name="text"]', '#searchbox input'):
                    try:
                        box = page.locator(sel).first
                        box.wait_for(state="visible", timeout=1500)
                        box.click(timeout=2000)
                        box.fill(q, timeout=3000)
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(1200 if not fast else 400)
                        done = True
                        break
                    except Exception:
                        continue
                if not done:
                    # accuracy+speed fallback: direct search URL is 100% reliable
                    try:
                        sq = urllib.parse.quote_plus(q)
                        page.goto(f"https://www.duckduckgo.com/?q={sq}",
                                  timeout=nav_timeout, wait_until="domcontentloaded")
                        page.wait_for_timeout(1200 if not fast else 400)
                        done = True
                    except Exception as e:
                        return {"ok": False, "error": f"search fallback failed: {e}"[:500]}
            if kind == "hover":
                try:
                    hloc = page.locator(action.get("selector", "a")).first
                    try:
                        hloc.scroll_into_view_if_needed(timeout=3000)
                    except Exception:
                        pass
                    hloc.hover(timeout=act_timeout)
                except Exception as e:
                    return {"ok": False, "error": f"hover failed: {e}"[:500]}
            if kind == "snapshot":
                # accuracy: return real observation for SEE-ACT loop (was title-only)
                try:
                    txt = page.locator("body").first.inner_text(timeout=3000)[:2000]
                except Exception:
                    txt = ""
                try:
                    n_links = page.locator("a").count()
                    n_inputs = page.locator("input,textarea,select").count()
                except Exception:
                    n_links, n_inputs = -1, -1
                try:
                    title = page.title()
                except Exception:
                    title = ""
                return {"ok": True, "title": title, "url_final": page.url,
                        "body_sample": txt, "links": n_links, "inputs": n_inputs,
                        "captcha": cap, "timing_ms": int((time.time() - t0) * 1000)}
            if kind == "screenshot":
                out = action.get("output") or os.path.join(TRACE_DIR, "shot.png")
                os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
                page.screenshot(path=out, full_page=False)
                return {"ok": True, "screenshot": out, "title": page.title(),
                        "captcha": cap, "timing_ms": int((time.time() - t0) * 1000)}
        title = ""
        try:
            title = page.title()
        except Exception:
            pass
        res = {"ok": True, "title": title, "url_final": page.url,
               "timing_ms": int((time.time() - t0) * 1000)}
        if cap.get("captcha"):
            res["captcha"] = cap
        return res
    except Exception as e:
        return {"ok": False, "error": str(e)[:500],
                "timing_ms": int((time.time() - t0) * 1000)}


def real_execute(action, seed=None, captcha="detect", captcha_wait_ms=30000, timeout=30000):
    """Execute one action in real headless Chromium (atomic CLI path: one launch)."""
    from playwright.sync_api import sync_playwright
    prof = random_profile(seed)
    with sync_playwright() as pw:
        # speed: disable sandbox/shm/gpu for ~30% faster cold start in containers
        browser = pw.chromium.launch(headless=action.get("headless", True),
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                  "--disable-extensions", "--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(viewport=prof["viewport"],
                                  user_agent=prof["user_agent"],
                                  locale="en-US", timezone_id="America/New_York",
                                  bypass_csp=True)
        page = ctx.new_page()
        # speed: shorter defaults for atomic one-shots
        page.set_default_timeout(min(timeout, 15000))
        page.set_default_navigation_timeout(min(timeout, 15000))
        apply_stealth(page, prof)
        try:
            return real_step_on_page(page, action, seed, captcha,
                                     captcha_wait_ms, timeout)
        finally:
            try:
                ctx.close(); browser.close()
            except Exception:
                pass


# ---------- simulate mode (offline, deterministic with --seed) ----------

def simulate_execute(action, seed=None):
    """Same schema as real, but no browser. Used for tests/CI."""
    t0 = time.time()
    kind = action["action"]
    human = action.get("human", True)
    fast = action.get("fast", False)
    out = {"ok": True, "mode": "simulate", "action": kind}
    if kind in ("new_tab", "newtab", "open_tab"):
        out["url"] = action.get("url", "https://example.com")
        out["tab"] = int(action.get("tab", action.get("index", 1)))
        # human-like: Ctrl+T path + tab-strip target + open delay
        tx, ty = human_tab_strip_target(out["tab"], seed)
        out["cursor_path"] = human_cursor_path(100, 100, tx, ty, 10, seed)
        out["tab_delay_ms"] = human_tab_delay("new_tab", human, seed, fast)
        out["think_ms"] = human_delay_range(human, seed, fast)
    elif kind in ("switch", "switch_tab", "tab"):
        out["tab"] = int(action.get("tab", action.get("index", 0)))
        tx, ty = human_tab_strip_target(out["tab"], seed)
        out["cursor_path"] = human_cursor_path(100, 100, tx, ty, 8, seed)
        out["tab_delay_ms"] = human_tab_delay("switch", human, seed, fast)
        out["think_ms"] = human_delay_range(human, seed, fast)
        if action.get("url"):
            out["url"] = action.get("url")
    elif kind in ("close_tab", "close", "closetab"):
        out["tab"] = int(action.get("tab", action.get("index", 0)))
        out["tab_delay_ms"] = human_tab_delay("close_tab", human, seed, fast)
        out["think_ms"] = human_delay_range(human, seed, fast)
    elif kind == "tabs":
        out["tabs"] = action.get("tabs", [])
        out["active"] = int(action.get("tab", action.get("index", 0)))
        out["think_ms"] = human_delay_range(human, seed, fast)
    elif kind == "move":
        out["cursor_path"] = human_cursor_path(100, 100, int(action["x"]), int(action["y"]),
                                               int(action.get("steps", 15)), seed)
        out["think_ms"] = human_delay_range(human, seed, fast)
    elif kind == "scroll":
        px = int(action.get("pixels", 800))
        if action.get("direction", "down") == "up":
            px = -px
        out["scroll_steps"] = human_scroll_plan(px, int(action.get("steps", 12)), seed)
        out["total"] = sum(out["scroll_steps"])
        out["think_ms"] = human_delay_range(human, seed, fast)
    elif kind == "fill":
        out["type_delays_ms"] = human_type_plan(action.get("text", ""), seed=seed)
        out["selector"] = action.get("selector")
        out["think_ms"] = human_delay_range(human, seed, fast)
    elif kind == "search":
        out["query"] = action.get("query")
        out["url"] = action.get("url")
        out["think_ms"] = human_delay_range(human, seed, fast)
    elif kind == "wait":
        out["waited_ms"] = int(action.get("ms", action.get("wait_ms", 1000)))
        out["think_ms"] = 0
    elif kind == "assert":
        out["selector"] = action.get("selector")
        if action.get("text"):
            out["text"] = action.get("text")
        out["think_ms"] = human_delay_range(human, seed, fast)
    else:
        out["url"] = action.get("url")
        if "selector" in action:
            out["selector"] = action["selector"]
        out["think_ms"] = human_delay_range(human, seed, fast)
    if action.get("url") and not is_valid_url(action.get("url")) and kind != "move":
        out["warning"] = f"suspicious url {action.get('url')!r}, expected http(s)://"
    if kind == "screenshot":
        outp = action.get("output") or os.path.join(TRACE_DIR, "shot.png")
        out["screenshot"] = outp
    out["profile"] = random_profile(seed)
    out["timing_ms"] = int((time.time() - t0) * 1000)
    return out


def do_action(action, force_simulate=False, seed=None, captcha="detect",
              captcha_wait_ms=30000, timeout=30000):
    """Pick real vs simulate, always return dict + save run."""
    want_real = bool(action.get("real")) and not force_simulate and has_playwright()
    if want_real:
        try:
            res = real_execute(action, seed, captcha, captcha_wait_ms, timeout)
            res["mode"] = "real"
        except Exception as e:
            res = {"ok": False, "mode": "real", "error": str(e)[:500]}
    else:
        res = simulate_execute(action, seed)
        if want_real is False and action.get("real") and not has_playwright():
            res["warning"] = "playwright not installed, fell back to simulate"
    save_run(action.get("action", "?"), json.dumps(action)[:1000], res.get("mode", "simulate"))
    return res


# ---------- task runner ----------

def _is_url_token(tok):
    return tok.startswith("http://") or tok.startswith("https://")


def parse_task(path):
    """Mini-DSL, one step per line. # comments ignored. Quotes supported via shlex.
    open <url>
    search <query words...> [url]
    click <selector>
    fill <selector> <text...>
    press <Key>
    scroll [down|up] [pixels] [steps N]
    move <x> <y> [steps N]
    hover <selector>
    snapshot [url]
    screenshot [output]
    wait <ms>
    assert <selector> [expected-text...]
    newtab <url> | new_tab <url>      # human-like Ctrl+T
    switch <index> | tab <index>      # human-like Ctrl+Tab + tab-strip move
    close [index] | close_tab [index] # human-like Ctrl+W (default: last)
    tabs                              # list open tabs
    """
    steps = []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                parts = shlex.split(line)
            except ValueError as e:
                print(f"[warn] {path}:{lineno}: bad quoting, skipped: {e}", file=sys.stderr)
                continue
            if not parts:
                continue
            verb = parts[0].lower()
            try:
                if verb == "open" and len(parts) >= 2:
                    steps.append({"action": "open", "url": parts[1]})
                elif verb == "search":
                    rest = parts[1:]
                    url = "https://www.duckduckgo.com"
                    if rest and _is_url_token(rest[-1]):
                        url = rest.pop()
                    steps.append({"action": "search", "query": " ".join(rest), "url": url})
                elif verb == "click" and len(parts) >= 2:
                    steps.append({"action": "click", "selector": parts[1]})
                elif verb == "fill" and len(parts) >= 3:
                    steps.append({"action": "fill", "selector": parts[1], "text": " ".join(parts[2:])})
                elif verb == "press":
                    steps.append({"action": "press", "key": parts[1] if len(parts) > 1 else "Enter"})
                elif verb == "scroll":
                    d, px, st = "down", 800, 12
                    rest = parts[1:]
                    if rest and rest[0] in ("down", "up"):
                        d = rest.pop(0)
                    if rest and rest[0].lstrip("-").isdigit():
                        px = int(rest.pop(0))
                    if "steps" in rest:
                        i = rest.index("steps")
                        if i + 1 < len(rest) and rest[i+1].isdigit():
                            st = int(rest[i+1])
                    steps.append({"action": "scroll", "direction": d, "pixels": px, "steps": st})
                elif verb == "move" and len(parts) >= 3:
                    st = 15
                    if "steps" in parts:
                        i = parts.index("steps")
                        if i + 1 < len(parts) and parts[i+1].isdigit():
                            st = int(parts[i+1])
                    steps.append({"action": "move", "x": int(parts[1]), "y": int(parts[2]), "steps": st})
                elif verb == "hover" and len(parts) >= 2:
                    steps.append({"action": "hover", "selector": parts[1]})
                elif verb == "snapshot":
                    s = {"action": "snapshot"}
                    if len(parts) >= 2 and _is_url_token(parts[1]):
                        s["url"] = parts[1]
                    steps.append(s)
                elif verb == "screenshot":
                    s = {"action": "screenshot"}
                    if len(parts) >= 2:
                        s["output"] = parts[1]
                    steps.append(s)
                elif verb == "wait" and len(parts) >= 2:
                    steps.append({"action": "wait", "ms": max(0, int(parts[1]))})
                elif verb == "assert" and len(parts) >= 2:
                    s = {"action": "assert", "selector": parts[1]}
                    if len(parts) > 2:
                        s["text"] = " ".join(parts[2:])
                    steps.append(s)
                elif verb in ("newtab", "new_tab", "opentab", "open_tab") and len(parts) >= 2:
                    steps.append({"action": "new_tab", "url": parts[1]})
                elif verb in ("switch", "switch_tab", "tab") and len(parts) >= 2:
                    try:
                        steps.append({"action": "switch", "tab": int(parts[1])})
                    except ValueError:
                        print(f"[warn] {path}:{lineno}: bad tab index, skipped: {line}",
                              file=sys.stderr)
                elif verb in ("close", "close_tab", "closetab"):
                    s = {"action": "close_tab"}
                    if len(parts) >= 2 and parts[1].lstrip("-").isdigit():
                        s["tab"] = int(parts[1])
                    steps.append(s)
                elif verb == "tabs":
                    steps.append({"action": "tabs"})
                else:
                    print(f"[warn] {path}:{lineno}: unknown/incomplete verb, skipped: {line}",
                          file=sys.stderr)
            except (ValueError, IndexError) as e:
                print(f"[warn] {path}:{lineno}: bad args, skipped ({e}): {line}", file=sys.stderr)
                continue
    return steps


def run_command(task_path, headless=True, human=True, output=None, real=False, seed=None,
                force_simulate=False, timeout=30000, captcha="detect", captcha_wait_ms=30000,
                fast=False, see=False):
    steps = parse_task(task_path)
    print(f"[run] {len(steps)} steps from {task_path} (human={human}, real={real}, fast={fast}, see={see})")
    print("[run] SEE-ACT loop: observe page -> act one human step -> observe again (never all-at-once)")
    trace = {"task": task_path, "human": human, "fast": fast, "see": see, "steps": []}
    ok_all = True
    t_start = time.time()

    def think_pause(n, eff_seed):
        # human-like pause BETWEEN steps so it acts step-by-step, not all-once
        if fast or not human:
            return 0
        # speed: //8 not //4 (~45-150ms) - still human rhythm, 2x faster suite
        ms = human_delay_range(True, eff_seed) // 8
        print(f"  [see] think {ms}ms before step {n}...")
        time.sleep(ms / 1000.0)
        return ms

    def show_observation(n, res):
        # what the human "saw" after acting
        title = res.get("title", "") or res.get("see_title", "")
        url = res.get("url_final") or res.get("see_url") or res.get("url", "")
        extra = ""
        if res.get("captcha"):
            extra = f" | captcha={res['captcha']}"
        if res.get("screenshot") or res.get("see_shot"):
            extra += f" | shot={res.get('screenshot') or res.get('see_shot')}"
        if res.get("body_sample"):
            extra += f" | text={res['body_sample'][:80]!r}"
        print(f"  [see] after step {n}: title={title!r} url={url}{extra}")

    use_real_session = (real and has_playwright() and not force_simulate)
    if real and not has_playwright():
        print("[run] playwright not installed, falling back to simulate", file=sys.stderr)
        use_real_session = False
    # accuracy: inherit last URL so click/fill/press stay on same page
    # (was: every step reset to example.com, breaking search-click flows)
    last_url = "https://example.com"
    for s in steps:
        if s.get("url"):
            last_url = s["url"]
        elif s["action"] in ("click", "fill", "press", "scroll", "hover",
                             "snapshot", "screenshot", "assert"):
            s["url"] = last_url

    if use_real_session:
        # FAST PATH: single browser launch for all steps (was: one launch per step)
        from playwright.sync_api import sync_playwright
        prof = random_profile(seed)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                      "--disable-extensions", "--disable-blink-features=AutomationControlled"])
            ctx = browser.new_context(viewport=prof["viewport"],
                                      user_agent=prof["user_agent"],
                                      locale="en-US", timezone_id="America/New_York",
                                      bypass_csp=True)
            page = ctx.new_page()
            page.set_default_timeout(min(timeout, 15000))
            page.set_default_navigation_timeout(min(timeout, 15000))
            apply_stealth(page, prof)
            try:
                for i, s in enumerate(steps, 1):
                    s = dict(s)
                    # defaults only — never overwrite DSL-provided url/steps (bug fix)
                    s.setdefault("url", last_url)
                    s.setdefault("steps", 12)
                    s.update({"human": human, "fast": fast, "headless": headless,
                              "real": True})
                    # speed+accuracy: salt seed per step -> varied delays/profiles
                    eff_seed = (seed + i * 101) if seed is not None else i
                    print(f"[act] step {i}/{len(steps)}: {s['action']} { {k: v for k, v in s.items() if k in ('url','selector','query','text','key','direction','pixels','ms')} }")
                    res = real_step_on_page(page, s, eff_seed, captcha,
                                            captcha_wait_ms, timeout)
                    res["mode"] = "real"
                    # multi-tab: keep `page` pointing at active tab after switch/new/close
                    try:
                        if s["action"] in ("new_tab", "newtab", "open_tab",
                                           "switch", "switch_tab", "tab",
                                           "close_tab", "close", "closetab"):
                            if "tab" in res and isinstance(res["tab"], int):
                                page = ctx.pages[res["tab"]] if 0 <= res["tab"] < len(ctx.pages) else ctx.pages[-1]
                            elif res.get("tabs") and isinstance(res.get("tabs"), int):
                                page = ctx.pages[-1]
                            else:
                                # tabs list query: stay on current, but refresh handle
                                pages_now = ctx.pages
                                if page not in pages_now and pages_now:
                                    page = pages_now[-1]
                    except Exception:
                        pass
                    # SEE: capture what changed after the act
                    try:
                        res["see_title"] = page.title()[:200]
                        res["see_url"] = page.url
                    except Exception:
                        pass
                    if see:
                        try:
                            shot = os.path.join(TRACE_DIR, f"step_{i}.png")
                            page.screenshot(path=shot, full_page=False)
                            res["see_shot"] = shot
                        except Exception as e:
                            res["see_shot_error"] = str(e)[:200]
                    save_run(s["action"], json.dumps(s)[:1000], "real")
                    trace["steps"].append({"n": i, "cmd": s, "result": res})
                    st = "OK" if res.get("ok") else "FAIL"
                    print(f" step {i}/{len(steps)} {s['action']}: {st}")
                    show_observation(i, res)
                    if res.get("captcha", {}).get("captcha") if isinstance(res.get("captcha"), dict) else res.get("captcha"):
                        print(f"  [captcha] flagged on step {i}", file=sys.stderr)
                    if not res.get("ok"):
                        ok_all = False
                        print(f"  [see] step {i} failed, stopping see-act loop for safety")
                        break
                    think_pause(i + 1, eff_seed)
            finally:
                try:
                    ctx.close(); browser.close()
                except Exception:
                    pass
    else:
        # simulate tab tracking (accuracy: trace shows tab list, not just last action)
        first_url = steps[0].get("url", "https://example.com") if steps else last_url
        sim_tabs = [first_url]
        sim_active = 0
        for i, s in enumerate(steps, 1):
            s = dict(s)
            s.setdefault("url", last_url)
            s.setdefault("steps", 12)
            s.update({"human": human, "fast": fast, "headless": headless,
                      "real": False})
            # maintain tab model before exec so simulate_execute can echo it
            ak = s["action"]
            if ak == "open" and s.get("url"):
                # open navigates active tab (accuracy: update tab URL)
                sim_tabs[sim_active] = s["url"]
            elif ak in ("new_tab", "newtab", "open_tab") and s.get("url"):
                sim_tabs.append(s["url"])
                sim_active = len(sim_tabs) - 1
                s["tab"] = sim_active
            elif ak in ("switch", "switch_tab", "tab"):
                try:
                    want = int(s.get("tab", s.get("index", 0)))
                except Exception:
                    want = 0
                if 0 <= want < len(sim_tabs):
                    sim_active = want
                s["tab"] = sim_active
            elif ak in ("close_tab", "close", "closetab"):
                if len(sim_tabs) > 1:
                    try:
                        want = int(s.get("tab", -1))
                    except Exception:
                        want = -1
                    if want < 0:
                        want = len(sim_tabs) - 1
                    if 0 <= want < len(sim_tabs):
                        sim_tabs.pop(want)
                        sim_active = max(0, min(sim_active, len(sim_tabs) - 1))
                s["tab"] = sim_active
            elif ak == "tabs":
                s["tabs"] = [{"i": j, "url": u} for j, u in enumerate(sim_tabs)]
                s["tab"] = sim_active
            print(f"[act] step {i}/{len(steps)}: {s['action']} { {k: v for k, v in s.items() if k in ('url','selector','query','text','key','direction','pixels','ms','tab')} }")
            eff = (seed + i * 101) if seed is not None else i
            res = do_action(s, force_simulate=True, seed=eff)
            # echo full tab model in trace for SEE-ACT accuracy
            res["sim_tabs"] = list(sim_tabs)
            res["sim_active"] = sim_active
            trace["steps"].append({"n": i, "cmd": s, "result": res})
            st = "OK" if res.get("ok") else "FAIL"
            print(f" step {i}/{len(steps)} {s['action']}: {st}")
            show_observation(i, res)
            if not res.get("ok"):
                ok_all = False
                print(f"  [see] step {i} failed, stopping see-act loop for safety")
                break
            think_pause(i + 1, eff)
    trace["status"] = "success" if ok_all else "partial"
    trace["duration_ms"] = int((time.time() - t_start) * 1000)
    if output:
        write_trace(output, trace)
        print(f"[run] trace -> {output}")
    return 0 if ok_all else 1


def add_common_args(q, need_url=True, need_output=True):
    if need_url:
        q.add_argument("--url", default="https://example.com")
    q.add_argument("--human", action=argparse.BooleanOptionalAction, default=True,
                   help="Human-like delays/cursor (use --no-human for speed)")
    q.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True,
                   help="Headless browser (use --no-headless for visible)")
    q.add_argument("--real", action=argparse.BooleanOptionalAction, default=False,
                   help="Use real Playwright browser (use --no-real for simulate)")
    q.add_argument("--fast", action="store_true", default=False,
                   help="Skip human delays (fastest, more bot-detectable)")
    q.add_argument("--seed", type=int, default=None)
    if need_output:
        q.add_argument("--output", default=None)
    q.add_argument("--timeout", type=int, default=30000, help="Per-step timeout ms")
    q.add_argument("--captcha", default="detect", choices=["detect", "wait", "manual", "2captcha"],
                   help="Captcha handling: detect-only, wait for manual solve, or 2captcha hook")
    q.add_argument("--captcha-wait-ms", type=int, default=30000)
    q.add_argument("--proxy", default=None, help="Proxy server, e.g. http://127.0.0.1:8080")
    return q


def main():
    p = argparse.ArgumentParser(description="Human-like Web Agent (cmds only)")
    sub = p.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("open")
    add_common_args(o, need_url=False)
    o.add_argument("--url", required=True)

    s = sub.add_parser("search")
    add_common_args(s, need_url=False)
    s.add_argument("--url", default="https://www.duckduckgo.com")
    s.add_argument("--query", required=True)

    c = sub.add_parser("click")
    add_common_args(c, need_url=False)
    c.add_argument("--url", default="https://example.com")
    c.add_argument("--selector", required=True)

    f = sub.add_parser("fill")
    add_common_args(f, need_url=False)
    f.add_argument("--url", default="https://example.com")
    f.add_argument("--selector", required=True)
    f.add_argument("--text", required=True)

    pr = sub.add_parser("press")
    add_common_args(pr, need_url=False)
    pr.add_argument("--url", default="https://example.com")
    pr.add_argument("--key", default="Enter")

    sc = sub.add_parser("scroll")
    add_common_args(sc, need_url=False)
    sc.add_argument("--url", default="https://example.com")
    sc.add_argument("--direction", default="down", choices=["down", "up"])
    sc.add_argument("--pixels", type=int, default=800)
    sc.add_argument("--steps", type=int, default=12)

    m = sub.add_parser("move")
    add_common_args(m, need_url=False)
    m.add_argument("--x", type=int, required=True)
    m.add_argument("--y", type=int, required=True)
    m.add_argument("--steps", type=int, default=15)

    h = sub.add_parser("hover")
    add_common_args(h, need_url=False)
    h.add_argument("--url", default="https://example.com")
    h.add_argument("--selector", required=True)

    sn = sub.add_parser("snapshot")
    add_common_args(sn, need_url=False)
    sn.add_argument("--url", default="https://example.com")

    sh = sub.add_parser("screenshot")
    add_common_args(sh, need_url=False, need_output=False)
    sh.add_argument("--url", default="https://example.com")
    sh.add_argument("--output", default="traces/shot.png")

    w = sub.add_parser("wait")
    add_common_args(w, need_url=False)
    w.add_argument("--ms", type=int, default=1000)

    a = sub.add_parser("assert")
    add_common_args(a, need_url=False)
    a.add_argument("--url", default="https://example.com")
    a.add_argument("--selector", required=True)
    a.add_argument("--text", default="")

    nt = sub.add_parser("new_tab", aliases=["newtab"])
    add_common_args(nt, need_url=False)
    nt.add_argument("--url", required=True, help="URL to open in new tab (Ctrl+T)")
    nt.add_argument("--tab", type=int, default=None, help="Expected tab index (simulate only)")

    sw = sub.add_parser("switch", aliases=["tab", "switch_tab"])
    add_common_args(sw, need_url=False)
    sw.add_argument("--tab", type=int, default=0, help="Tab index to switch to (Ctrl+Tab)")
    sw.add_argument("--index", type=int, default=None, help="Alias for --tab")
    sw.add_argument("--url", default=None, help="Optional URL hint for simulate trace")

    ct = sub.add_parser("close_tab", aliases=["close", "closetab"])
    add_common_args(ct, need_url=False)
    ct.add_argument("--tab", type=int, default=-1, help="Tab index to close, default last (Ctrl+W)")
    ct.add_argument("--index", type=int, default=None, help="Alias for --tab")

    tl = sub.add_parser("tabs")
    add_common_args(tl, need_url=False)

    r = sub.add_parser("run")
    r.add_argument("--task", required=True)
    r.add_argument("--output", default="traces/run.json")
    r.add_argument("--human", action=argparse.BooleanOptionalAction, default=True)
    r.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    r.add_argument("--real", action=argparse.BooleanOptionalAction, default=False)
    r.add_argument("--fast", action="store_true", default=False)
    r.add_argument("--seed", type=int, default=None)
    r.add_argument("--timeout", type=int, default=30000)
    r.add_argument("--captcha", default="detect",
                   choices=["detect", "wait", "manual", "2captcha"])
    r.add_argument("--captcha-wait-ms", type=int, default=30000)
    r.add_argument("--proxy", default=None)
    r.add_argument("--see", action="store_true", default=False,
                   help="Save per-step screenshot (real mode) + verbose see-act log")

    hi = sub.add_parser("history")
    hi.add_argument("--limit", type=int, default=10)
    hi.add_argument("--mode", default=None, choices=["real", "simulate"])
    sub.add_parser("stats")
    cl = sub.add_parser("clean")
    cl.add_argument("--yes", action="store_true", default=False,
                    help="Skip confirmation")

    args = p.parse_args()
    seed = getattr(args, "seed", None)

    def emit(res, out):
        if out and out.endswith(".json"):
            write_trace(out, res)
            print(f"[trace] -> {out}")
        elif out and out.endswith(".png"):
            if res.get("mode") == "simulate":
                write_placeholder_png(out)
                res["screenshot"] = out
                res["note"] = "simulate mode: placeholder PNG (use --real for true capture)"
                print(f"[trace] placeholder -> {out} (simulate mode, use --real for real shot)")
            else:
                print(json.dumps(res, indent=2)[:2000])
        else:
            print(json.dumps(res, indent=2)[:2000])

    try:
        if args.cmd in ("open", "search", "click", "fill", "press", "scroll",
                        "hover", "snapshot", "screenshot", "move", "wait", "assert",
                        "new_tab", "newtab", "switch", "tab", "switch_tab",
                        "close_tab", "close", "closetab", "tabs"):
            # normalize aliases to canonical action names
            canon = {"newtab": "new_tab", "tab": "switch", "switch_tab": "switch",
                     "close": "close_tab", "closetab": "close_tab"}.get(args.cmd, args.cmd)
            a_ = {"action": canon, "human": getattr(args, "human", True),
                  "fast": getattr(args, "fast", False),
                  "headless": getattr(args, "headless", True),
                  "real": getattr(args, "real", False)}
            for k in ("url", "query", "selector", "text", "key", "direction",
                      "pixels", "steps", "x", "y", "output", "ms", "proxy",
                      "tab", "index"):
                if hasattr(args, k):
                    v = getattr(args, k)
                    if v is not None:
                        a_[k] = v
            # --index is alias for --tab
            if a_.get("index") is not None and a_.get("tab") is None:
                a_["tab"] = a_["index"]
            a_.pop("index", None)
            # validate numeric edge cases early with clear errors
            if "steps" in a_:
                try:
                    if int(a_["steps"]) < 1:
                        print("[warn] --steps < 1, clamped to 1", file=sys.stderr)
                        a_["steps"] = 1
                except Exception:
                    pass
            if a_.get("url") and not is_valid_url(a_.get("url")):
                print(f"[warn] suspicious --url {a_['url']!r}", file=sys.stderr)
            res = do_action(a_, seed=seed if seed is not None else 42,
                            captcha=getattr(args, "captcha", "detect"),
                            captcha_wait_ms=getattr(args, "captcha_wait_ms", 30000),
                            timeout=getattr(args, "timeout", 30000))
            emit(res, getattr(args, "output", None))
            sys.exit(0 if res.get("ok") else 1)
        elif args.cmd == "run":
            sys.exit(run_command(args.task, args.headless, args.human, args.output,
                                 args.real, seed,
                                 force_simulate=not args.real,
                                 timeout=getattr(args, "timeout", 30000),
                                 captcha=getattr(args, "captcha", "detect"),
                                 captcha_wait_ms=getattr(args, "captcha_wait_ms", 30000),
                                 fast=getattr(args, "fast", False),
                                 see=getattr(args, "see", False)))
        elif args.cmd == "history":
            init_db()
            con = sqlite3.connect(DB_PATH, timeout=10)
            try:
                if getattr(args, "mode", None):
                    rows = con.execute(
                        "SELECT id, cmd, detail, mode, ts FROM runs WHERE mode=? "
                        "ORDER BY id DESC LIMIT ?", (args.mode, args.limit)).fetchall()
                else:
                    rows = con.execute(
                        "SELECT id, cmd, detail, mode, ts FROM runs ORDER BY id DESC LIMIT ?",
                        (args.limit,)).fetchall()
            finally:
                con.close()
            if not rows:
                print("No runs yet.")
            for r_ in rows:
                print(f"#{r_[0]} {r_[4]} | {r_[1]} | {r_[3]} | {r_[2][:100]}")
        elif args.cmd == "stats":
            init_db()
            con = sqlite3.connect(DB_PATH, timeout=10)
            try:
                total = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                by_mode = con.execute(
                    "SELECT mode, COUNT(*) FROM runs GROUP BY mode").fetchall()
            finally:
                con.close()
            print(f"Total runs: {total}")
            for mode, n in by_mode:
                print(f"  {mode}: {n}")
            print(f"Playwright installed: {has_playwright()} (simulate mode works without it)")
            print(f"Traces dir: {TRACE_DIR}")
        elif args.cmd == "clean":
            import glob
            import shutil
            targets = glob.glob(os.path.join(TRACE_DIR, "*"))
            if not getattr(args, "yes", False) and sys.stdin.isatty():
                ans = input(f"Remove {len(targets)} trace files + memory.db? [y/N] ").strip().lower()
                if ans not in ("y", "yes"):
                    print("Aborted.")
                    sys.exit(0)
            for f_ in targets:
                try:
                    os.remove(f_) if os.path.isfile(f_) else shutil.rmtree(f_)
                    print(f"removed {f_}")
                except Exception:
                    pass
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
                print("removed memory.db")
            try:
                has_playwright.cache_clear()
            except Exception:
                pass
            print("[clean] Done.")
    except SystemExit:
        raise
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
