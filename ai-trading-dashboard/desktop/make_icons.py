"""Genera le icone dell'app (PNG, ICO per Windows, ICNS per Mac). Uso: python desktop/make_icons.py"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent
S = 1024


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = 92  # margine come le icone macOS
    d.rounded_rectangle([m, m, S - m, S - m], radius=190, fill=(22, 26, 32, 255))
    # griglia leggera
    for i in range(1, 4):
        y = m + (S - 2 * m) * i / 4
        d.line([(m + 70, y), (S - m - 70, y)], fill=(44, 50, 60, 255), width=6)
    # candele stilizzate
    candles = [(300, 560, 640, 470, 690, False), (420, 500, 600, 430, 640, True), (540, 520, 440, 400, 560, True), (660, 420, 330, 290, 470, True)]
    for x, o, c, hi, lo, up in candles:
        col = (28, 98, 94, 255) if up else (140, 58, 58, 255)
        d.line([(x, hi), (x, lo)], fill=col, width=10)
        d.rounded_rectangle([x - 32, min(o, c), x + 32, max(o, c)], radius=8, fill=col)
    # linea del momentum
    pts = [(220, 700), (380, 560), (500, 630), (790, 300)]
    d.line(pts, fill=(38, 166, 154, 255), width=58, joint="curve")
    for p in (pts[0], pts[-1]):
        d.ellipse([p[0] - 29, p[1] - 29, p[0] + 29, p[1] + 29], fill=(38, 166, 154, 255))
    return img


if __name__ == "__main__":
    img = draw()
    img.save(OUT / "icon.png")
    img.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    img.save(OUT / "icon.icns")
    print("Icone create in", OUT)
