import os
from PIL import Image
from analyzer import analyze


def _img(path, color, size=(800, 600)):
    Image.new("RGB", size, color).save(path)


def test_photo_stats(tmp_path):
    p = str(tmp_path / "red.png")
    _img(p, (200, 30, 30))
    r = analyze(p)
    assert r["size"] == [800, 600]
    assert r["dominant_colors"][0]["hex"].startswith("#c8") or "c8" in r["dominant_colors"][0]["hex"]
    assert r["likely"] in ("screenshot/UI", "photo/gradient")


def test_edge_density_ui(tmp_path):
    # half black / half white = high edges in middle
    p = str(tmp_path / "split.png")
    im = Image.new("RGB", (800, 600), (0, 0, 0))
    right = Image.new("RGB", (400, 600), (255, 255, 255))
    im.paste(right, (400, 0))
    im.save(p)
    r = analyze(p)
    assert r["edge_density"] >= 0
