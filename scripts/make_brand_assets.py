"""Cut the Flowbit mascot and wordmark out of the approved logo image (white background -> transparent).

  .\\.venv\\Scripts\\python.exe scripts\\make_brand_assets.py <logo image>

Writes voicetype\\assets\\flowbit_mascot.png and flowbit_wordmark.png (committed, so the app needs no image at run time).
"""
import sys
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QImageReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "voicetype" / "assets"
# regions of the 1256 px logo (checked by eye on the full image)
MASCOT = QRect(330, 245, 570, 565)  # wider margin: the smoke is faded out towards this edge
EDGE_FADE = 44  # px (in the 1256 px logo) over which the mascot's smoke fades to transparent at the crop edge
WORDMARK = QRect(205, 800, 800, 195)


BRIGHT = 230  # a pixel at least this light (in every channel) is paper-white


def background_mask(img: QImage) -> bytearray:
    """1 where the paper-white background touches the image edge. White letters inside the logo are NOT
    connected to the edge (smoke separates them), so they are kept."""
    w, h = img.width(), img.height()

    def white(x, y):
        c = QColor(img.pixel(x, y))
        return min(c.red(), c.green(), c.blue()) >= BRIGHT

    mask = bytearray(w * h)
    stack = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] + [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]
    stack = [(x, y) for x, y in stack if white(x, y)]
    while stack:
        x, y = stack.pop()
        i = y * w + x
        if mask[i]:
            continue
        mask[i] = 1
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not mask[ny * w + nx] and white(nx, ny):
                stack.append((nx, ny))
    return mask


def to_alpha(img: QImage, soft: bool) -> QImage:
    """Background becomes transparent. soft=True: grey smoke becomes a soft shadow (mascot). soft=False: everything
    else stays opaque (wordmark: no speckles inside the letters)."""
    out = img.convertToFormat(QImage.Format_ARGB32)
    mask = background_mask(out)
    w = out.width()
    for y in range(out.height()):
        for x in range(w):
            c = QColor(out.pixel(x, y))
            if mask[y * w + x]:
                out.setPixel(x, y, QColor(c.red(), c.green(), c.blue(), 0).rgba())
                continue
            darkest = min(c.red(), c.green(), c.blue())
            alpha = max(0, min(255, int((255 - darkest) * 1.25))) if soft else 255
            if c.red() - c.blue() > 60 or darkest >= BRIGHT:  # orange glow, or the white letters: fully opaque
                alpha = 255
            edge = min(x, y, w - 1 - x, out.height() - 1 - y)  # no square edge: fade towards the crop boundary
            alpha = int(alpha * min(1.0, edge / EDGE_FADE))
            out.setPixel(x, y, QColor(c.red(), c.green(), c.blue(), alpha).rgba())
    return out


def main() -> None:
    QGuiApplication([])
    src = Path(sys.argv[1])
    reader = QImageReader(str(src))
    reader.setAutoTransform(True)
    full = reader.read()
    if full.isNull():
        sys.exit(f"could not read {src}")
    OUT.mkdir(parents=True, exist_ok=True)
    for rect, name, width, soft in ((MASCOT, "flowbit_mascot.png", 256, True), (WORDMARK, "flowbit_wordmark.png", 480, False)):
        part = to_alpha(full.copy(rect), soft)
        part = part.scaledToWidth(width, Qt.SmoothTransformation)
        part.save(str(OUT / name), "PNG")
        print(name, part.width(), "x", part.height())


if __name__ == "__main__":
    main()
