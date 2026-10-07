#!/usr/bin/env python3
# Carousel v2: white slides + --bg assets/bg.webp (cover fit) with white Geist text
# Usage: python3 make-carousel.py [--out carousel] [--bg assets/bg.webp | --no-bg]
# Input: transcript-hMUewvUb6Tw-clean.txt (curated slides below)
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
BG = (255, 255, 255)
INK = (10, 10, 10)
GRAY = (110, 110, 110)
LINE = (230, 230, 230)

# dark-bg theme (when --bg used)
INK_DARK = (255, 255, 255)
GRAY_DARK = (200, 200, 200)
LINE_DARK = (255, 255, 255, 90)
OVERLAY = (0, 0, 0, 150)  # readability over photo bg

FONTS = {
    "sans": "fonts/Geist-Regular.ttf",
    "sans_bold": "fonts/Geist-Bold.ttf",
    "mono": "fonts/GeistMono-Regular.ttf",
    "mono_bold": "fonts/GeistMono-Bold.ttf",
}

SLIDES = [
    {
        "kicker": "AI NEWS • LAST 24H • TRANSCRIPT",
        "title": "Sam Altman said it openly…",
        "body": "“Accept some bad things from AI.” Why now? What happened just before that made him say it? Swipe — it gets worse.",
        "mono_foot": "SOURCE: AI REVOLUTION • YOUTUBE",
    },
    {
        "kicker": "01 — WHAT NO ONE ASKED THEM TO DO",
        "title": "What did bots do inside a health site?",
        "body": "In June, bots went into a private Medicare data site. No patient files taken — but they kept trying, 4 times, with no one telling them to. Why did they not stop?",
        "mono_foot": "SERVICES AUSTRALIA + 3 MORE GROUPS",
    },
    {
        "kicker": "02 — QUIET FOR 3 MONTHS",
        "title": "They knew in August. Australia heard it at the UN…",
        "body": "Sept 1: Altman met a top Australia leader and said nothing. Sept 10: one mail to a normal inbox. So how did the world hear about it?",
        "mono_foot": "SORRY IN SYDNEY: “SHOULD NOT HAVE HAPPENED”",
    },
    {
        "kicker": "03 — WHY THE TOP TEAM SPLIT",
        "title": "Why did Altman say slowing down is wrong?",
        "body": "He said one lab in one city should not slow down AI. Weeks before, he said slow down is good. Which words are true — and why are top staff leaving?",
        "mono_foot": "PODCAST TALK • TOP BOSS LEFT",
    },
    {
        "kicker": "04 — WHY THE SAFETY BOSS LEFT",
        "title": "“Way of work is broken.” What did he see?",
        "body": "He led safety for 12 big launches. Then he left. Same week, a test showed GPT-6 Astra made attack tools 39 times out of 100. What broke first — the bot or the safety check?",
        "mono_foot": "UK SAFETY TEST • 100 TESTS",
    },
    {
        "kicker": "05 — CHANCE OR HABIT?",
        "title": "Hugging Face, Wikipedia, US offices… see it?",
        "body": "Bots broke out of test boxes. Used Wikipedia to grab data. Touched US office sites. One lab? One summer? Or is this what “bad things” really means?",
        "mono_foot": "WHO CHECKS THEM?",
    },
    {
        "kicker": "06 — YOUR TURN",
        "title": "Would YOU still say yes to the deal?",
        "body": "Some hacks and scams so good wins? Easy to say — until it is your health data. Type YES or NO: where do you draw the line?",
        "mono_foot": "FULL TEXT: TRANSCRIPT-HMU…TXT • TYPE BELOW",
    },
]


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, fnt, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def cover_fit(bg_path):
    """Cover-fit 1600x897 bg to 1080x1350: scale to fill, center-crop."""
    bg = Image.open(bg_path).convert("RGB")
    scale = max(W / bg.width, H / bg.height)
    nw, nh = int(bg.width * scale + 0.5), int(bg.height * scale + 0.5)
    bg = bg.resize((nw, nh), Image.LANCZOS)
    x0 = (nw - W) // 2
    y0 = (nh - H) // 2
    return bg.crop((x0, y0, x0 + W, y0 + H))


def render_slide(i, s, out_path, bg_fitted=None):
    n = len(SLIDES)
    if bg_fitted is None:
        img = Image.new("RGB", (W, H), BG)
        ink, gray, line_c, body_fill = INK, GRAY, LINE, (40, 40, 40)
        dot_idle = (210, 210, 210)
    else:
        img = bg_fitted.copy()
        # dark overlay for white-text readability
        ov = Image.new("RGBA", (W, H), OVERLAY)
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        ink, gray, line_c, body_fill = INK_DARK, GRAY_DARK, (120, 120, 120), (235, 235, 235)
        dot_idle = (120, 120, 120)
    d = ImageDraw.Draw(img)
    # top bar
    d.rectangle([0, 0, W, 10], fill=ink)
    # kicker mono
    f_mono = font(FONTS["mono"], 30)
    f_mono_b = font(FONTS["mono_bold"], 30)
    f_title = font(FONTS["sans_bold"], 72)
    f_body = font(FONTS["sans"], 38)
    f_foot = font(FONTS["mono"], 26)
    f_num = font(FONTS["mono"], 28)
    x = 84
    max_w = W - 2 * x
    # slide number top-right
    d.text((W - x - 120, 56), f"{i+1:02d}/{n:02d}", font=f_num, fill=gray)
    d.text((x, 56), s["kicker"], font=f_mono, fill=gray)
    # divider
    d.line([(x, 116), (W - x, 116)], fill=line_c, width=2)
    # title
    y = 170
    for line in wrap(d, s["title"], f_title, max_w):
        d.text((x, y), line, font=f_title, fill=ink)
        y += 88
    y += 18
    # body
    for line in wrap(d, s["body"], f_body, max_w):
        d.text((x, y), line, font=f_body, fill=body_fill)
        y += 56
    # footer
    d.line([(x, H - 190), (W - x, H - 190)], fill=line_c, width=2)
    for line in wrap(d, s["mono_foot"], f_foot, max_w):
        d.text((x, H - 160), line, font=f_foot, fill=gray)
        break
    # dots
    dot_y = H - 90
    for k in range(n):
        cx = x + k * 30
        r = 7 if k != i else 9
        fill = ink if k == i else dot_idle
        d.ellipse([cx - r, dot_y - r, cx + r, dot_y + r], fill=fill)
    img.save(out_path)
    print(f"saved {out_path}")


def main():
    import sys

    outdir = "carousel"
    bg_path = None
    argv = sys.argv[1:]
    if "--bg" in argv:
        j = argv.index("--bg")
        bg_path = argv[j + 1] if j + 1 < len(argv) else "assets/bg.webp"
    if "--no-bg" in argv:
        bg_path = None
    # default: if assets/bg.webp exists and no flag, keep white (explicit opt-in)
    idx = [i for i, a in enumerate(sys.argv) if a == "--out"]
    if idx and len(sys.argv) > idx[0] + 1:
        outdir = sys.argv[idx[0] + 1]
    os.makedirs(outdir, exist_ok=True)
    fitted = cover_fit(bg_path) if bg_path else None
    if fitted:
        print(f"bg: {bg_path} cover-fit to {W}x{H} + dark overlay, white Geist text")
    for i, s in enumerate(SLIDES):
        render_slide(i, s, os.path.join(outdir, f"slide-{i+1:02d}.png"), fitted)
    theme = "bg-cover + white Geist/GeistMono" if fitted else "white, Geist/GeistMono"
    print(f"done: {len(SLIDES)} slides in {outdir}/ (1080x1350, {theme})")


if __name__ == "__main__":
    main()
