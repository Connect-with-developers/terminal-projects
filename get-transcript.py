#!/usr/bin/env python3
# v1: Get YouTube transcript via real browser UI (Show transcript panel)
# Why UI: youtube-transcript-api + yt-dlp innertube are IP-blocked on cloud (RequestBlocked/429).
# Usage: python3 get-transcript.py <videoId|url> [--output file.txt]
# Example: python3 get-transcript.py hMUewvUb6Tw
#          python3 get-transcript.py "https://www.youtube.com/watch?v=hMUewvUb6Tw"
import re
import sys


def parse_id(s):
    m = re.search(r"(?:v=|youtu\.be/|/shorts/)([a-zA-Z0-9_-]{11})", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", s.strip()):
        return s.strip()
    raise ValueError(f"Cannot parse video id from {s!r}")


def clean_text(raw, url):
    import re

    re_ts = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
    re_dur = re.compile(
        r"^(\d+\s+(second|seconds|minute|minutes|hour|hours)(,\s*\d+\s+(second|seconds|minute|minutes))?)$",
        re.I,
    )
    lines = [l.strip() for l in raw.splitlines()]
    paras = []
    cur_chapter = None
    cur_buf = []

    def flush():
        if cur_buf:
            text = " ".join(cur_buf)
            text = re.sub(r"\[music\]", "", text, flags=re.I)
            text = re.sub(r"\s+", " ", text).strip()
            text = re.sub(r"\s+([.,!?;:])", r"\1", text)
            if text:
                paras.append((cur_chapter, text))
        cur_buf.clear()

    for ln in lines:
        if not ln:
            continue
        if ln.lower() in ("transcript", "search transcript"):
            continue
        if ln.startswith("Chapter "):
            flush()
            cur_chapter = ln
            continue
        if re_ts.match(ln) or re_dur.match(ln) or ln.startswith("Video:"):
            continue
        cur_buf.append(ln)
    flush()
    out = [url, ""]
    for ch, txt in paras:
        if ch:
            out += [ch, ""]
        out += [txt, ""]
    return "\n".join(out).strip() + "\n"


def main():
    want_clean = "--clean" in sys.argv
    args = [
        a
        for a in sys.argv[1:]
        if not a.startswith("--") or a == "--"
    ]
    args = [a for a in args if a != "--"]
    out = None
    for i, a in enumerate(sys.argv[1:]):
        if a == "--output" and i + 1 < len(sys.argv[1:]):
            out = sys.argv[1:][i + 1]
    if not args:
        print('Usage: python3 get-transcript.py <videoId|url> [--output file.txt]')
        sys.exit(1)
    vid = parse_id(args[0])
    url = f"https://www.youtube.com/watch?v={vid}"
    if not out:
        out = f"transcript-{vid}.txt"
    print(f"Video: {url}")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        ctx = b.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            locale="en-US",
        )
        p = ctx.new_page()
        p.goto(url, wait_until="domcontentloaded", timeout=45000)
        p.wait_for_timeout(4000)
        p.mouse.wheel(0, 600)
        p.wait_for_timeout(1500)
        try:
            p.locator("tp-yt-paper-button#expand").first.click(timeout=3000)
        except Exception:
            pass
        p.wait_for_timeout(1000)
        btns = p.get_by_text("Show transcript")
        clicked = False
        for i in range(btns.count()):
            try:
                if btns.nth(i).is_visible():
                    btns.nth(i).click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            print("ERROR: Show transcript button not found/visible")
            b.close()
            sys.exit(1)
        p.wait_for_timeout(6000)
        panels = p.locator("ytd-engagement-panel-section-list-renderer")
        best = ""
        for k in range(panels.count()):
            try:
                t = panels.nth(k).inner_text(timeout=5000)
                if len(t) > len(best) and "Transcript" in t:
                    best = t
            except Exception:
                continue
        b.close()

    if not best or len(best) < 200:
        print("ERROR: transcript panel empty (video may have no captions)")
        sys.exit(1)
    if want_clean:
        best = clean_text(best, f"Video: {url}")
        if not out or out.startswith("/tmp/"):
            pass
        # default clean suffix
        if "--output" not in sys.argv and out == f"transcript-{vid}.txt":
            out = f"transcript-{vid}-clean.txt"
    with open(out, "w", encoding="utf-8") as f:
        if best.startswith("Video:"):
            f.write(f"{best}\n")
        else:
            f.write(f"Video: {url}\n{best}\n")
    print(f"Saved {len(best)} chars to {out}")


if __name__ == "__main__":
    main()
