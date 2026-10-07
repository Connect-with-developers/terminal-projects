"""Lightweight image analyzer (your own images/screenshots only).
No cloud, no training needed: stats + colors + optional OCR.
"""
import json
import os
import sys

from PIL import Image, ImageStat


def dominant_colors(img, n=3):
    small = img.convert("RGB").resize((64, 64)).quantize(colors=n, method=2)
    pal = small.getpalette()[: n * 3]
    counts = sorted(small.getcolors(64 * 64), reverse=True)
    out = []
    for cnt, idx in counts[:n]:
        r, g, b = pal[idx*3:idx*3+3]
        out.append({"hex": f"#{r:02x}{g:02x}{b:02x}", "pixels": cnt})
    return out


def edge_density(gray):
    w, h = gray.size
    px = gray.load()
    diffs = 0
    total = 0
    for y in range(0, h - 1, 4):
        for x in range(0, w - 1, 4):
            total += 1
            if abs(px[x, y] - px[x+1, y]) + abs(px[x, y] - px[x, y+1]) > 60:
                diffs += 1
    return round(diffs / max(1, total), 3)


def try_ocr(path):
    try:
        import subprocess
        r = subprocess.run(["tesseract", path, "stdout"],
                           capture_output=True, text=True, timeout=20)
        txt = r.stdout.strip()
        return txt[:2000] if txt else None
    except Exception:
        return None


def analyze(path):
    img = Image.open(path).convert("RGB")
    gray = img.convert("L")
    stat = ImageStat.Stat(gray)
    w, h = img.size
    res = {
        "file": os.path.basename(path),
        "format": img.format or os.path.splitext(path)[1].lstrip("."),
        "size": [w, h],
        "megapixels": round(w * h / 1e6, 2),
        "brightness": round(stat.mean[0], 1),  # 0 dark - 255 bright
        "contrast": round(stat.stddev[0], 1),
        "dominant_colors": dominant_colors(img),
        "edge_density": edge_density(gray),  # high = text/UI, low = photo/gradient
        "likely": "screenshot/UI" if edge_density(gray) > 0.15 and w >= 800 else "photo/gradient",
    }
    ocr = try_ocr(path)
    res["ocr"] = ocr if ocr else "(tesseract not installed — pip/apt install for text)"
    return res


def main():
    if len(sys.argv) < 2:
        print("usage: python analyzer.py <image> [--json]")
        raise SystemExit(2)
    path = sys.argv[1]
    res = analyze(path)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
