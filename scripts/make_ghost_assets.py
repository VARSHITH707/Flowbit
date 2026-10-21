"""Build the ghost-mascot brand assets from the approved reference image (alpha verified, not assumed).

  .\\.venv\\Scripts\\python.exe scripts\\make_ghost_assets.py <reference.webp> <wordmark-source.webp>

Writes (voicetype\\assets):
  flowbit-mascot.png   square, transparent, 512 px: the ghost only
  flowbit-mascot.json  eye boxes (normalised 0..1 of the mascot square) for the blink animation
  flowbit-icon.png     256 px version for the taskbar, tray and .exe icon
  flowbit-logo.png     ghost above the Flowbit wordmark, transparent
and a report of the alpha checks it made.
"""
import json
import sys
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QImageReader, QPainter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "voicetype" / "assets"
SIZE = 512
ALPHA_FLOOR, ALPHA_CEIL = 10, 245  # alpha below the floor is background; above the ceiling is solid


def load(path: str) -> QImage:
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    img = reader.read()
    if img.isNull():
        sys.exit(f"cannot read {path}")
    return img.convertToFormat(QImage.Format_ARGB32)


DARK_HALO = 40  # channels at or below this, connected to the image edge, are the dark glow outside the character


def clean_alpha(img: QImage) -> QImage:
    """Remove the background: transparent pixels, plus the dark glow that touches the image edge (it would
    otherwise become black rectangular corners). The character's own dark body is enclosed by its orange rim
    and is not reached, so it is kept."""
    out = img.copy()
    w, h = out.width(), out.height()
    px = [QColor(out.pixel(x, y)) for y in range(h) for x in range(w)]

    def dark_halo(i: int) -> bool:
        c = px[i]
        return c.alpha() > ALPHA_FLOOR and max(c.red(), c.green(), c.blue()) <= DARK_HALO

    background = bytearray(w * h)
    stack = [i for i in range(w * h) if (i % w in (0, w - 1) or i // w in (0, h - 1)) and dark_halo(i)]
    for i in stack:
        background[i] = 1
    while stack:
        i = stack.pop()
        x, y = i % w, i // w
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h:
                j = ny * w + nx
                if not background[j] and dark_halo(j):
                    background[j] = 1
                    stack.append(j)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            c = px[i]
            a = 0 if (c.alpha() <= ALPHA_FLOOR or background[i]) else (255 if c.alpha() >= ALPHA_CEIL else c.alpha())
            out.setPixel(x, y, QColor(c.red(), c.green(), c.blue(), a).rgba())
    return out


def content_box(img: QImage) -> QRect:
    xs, ys = [], []
    step = 3
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            if img.pixelColor(x, y).alpha() > ALPHA_FLOOR:
                xs.append(x)
                ys.append(y)
    return QRect(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)


def square_around(box: QRect, img: QImage, pad: float = 0.04) -> QRect:
    side = int(max(box.width(), box.height()) * (1 + 2 * pad))
    cx, cy = box.center().x(), box.center().y()
    x0 = max(0, min(img.width() - side, cx - side // 2))
    y0 = max(0, min(img.height() - side, cy - side // 2))
    return QRect(x0, y0, min(side, img.width()), min(side, img.height()))


def find_eyes(img: QImage) -> list[tuple[int, int, int, int]]:
    """Bright orange eye arcs, found in the face band above the mouth. Returns two boxes (left, right)."""
    h = img.height()
    boxes = []
    for lo, hi in ((int(img.width() * 0.30), int(img.width() * 0.56)), (int(img.width() * 0.56), int(img.width() * 0.78))):
        xs, ys = [], []
        for y in range(int(h * 0.32), int(h * 0.455), 2):  # above the mouth
            for x in range(lo, hi, 2):
                c = img.pixelColor(x, y)
                if c.alpha() > 200 and c.red() > 200 and c.green() > 120 and c.blue() < 120:
                    xs.append(x)
                    ys.append(y)
        if not xs:
            sys.exit("eye detection found nothing: check the face region")
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    return boxes


def main() -> None:
    QGuiApplication([])
    ref = clean_alpha(load(sys.argv[1]))
    OUT.mkdir(parents=True, exist_ok=True)

    box = content_box(ref)
    sq = square_around(box, ref)
    mascot = ref.copy(sq).scaled(SIZE, SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    # the crop is square, so the scaled image is exactly SIZE x SIZE
    mascot = mascot.convertToFormat(QImage.Format_ARGB32)
    mascot.save(str(OUT / "flowbit-mascot.png"), "PNG")

    # eyes in mascot-normalised coordinates
    eyes = []
    for x0, y0, x1, y1 in find_eyes(ref):
        pad = 10
        nx0 = (x0 - pad - sq.x()) / sq.width()
        ny0 = (y0 - pad - sq.y()) / sq.height()
        nx1 = (x1 + pad - sq.x()) / sq.width()
        ny1 = (y1 + pad - sq.y()) / sq.height()
        eyes.append([round(nx0, 4), round(ny0, 4), round(nx1, 4), round(ny1, 4)])
    (OUT / "flowbit-mascot.json").write_text(json.dumps({"eyes": eyes, "size": SIZE}, indent=2), encoding="utf-8")

    icon = mascot.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    icon.save(str(OUT / "flowbit-icon.png"), "PNG")

    # logo: the ghost alone, no name (the name is not part of the logo)
    mascot.scaled(512, 512, Qt.KeepAspectRatio, Qt.SmoothTransformation).save(str(OUT / "flowbit-logo.png"), "PNG")

    # ---- report: the alpha is measured, not assumed
    def stats(im: QImage) -> dict:
        n = solid = partial = clear = 0
        corners = [im.pixelColor(0, 0).alpha(), im.pixelColor(im.width() - 1, 0).alpha(),
                   im.pixelColor(0, im.height() - 1).alpha(), im.pixelColor(im.width() - 1, im.height() - 1).alpha()]
        for y in range(0, im.height(), 4):
            for x in range(0, im.width(), 4):
                a = im.pixelColor(x, y).alpha()
                n += 1
                solid += a == 255
                clear += a == 0
                partial += 0 < a < 255
        return {"size": f"{im.width()}x{im.height()}", "corner_alpha": corners,
                "transparent_fraction": round(clear / n, 3), "solid_fraction": round(solid / n, 3),
                "soft_edge_fraction": round(partial / n, 3)}
    for name in ("flowbit-mascot.png", "flowbit-icon.png", "flowbit-logo.png"):
        print(name, stats(QImage(str(OUT / name))))
    print("eyes (normalised):", eyes)


if __name__ == "__main__":
    main()
