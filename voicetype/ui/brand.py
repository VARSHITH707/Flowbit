"""Flowbit brand images, shipped in voicetype/assets (committed, so no image is fetched at run time).

  flowbit-mascot.png   the ghost mascot, transparent (validated by scripts/make_ghost_assets.py)
  flowbit-mascot.json  the two eye boxes, as fractions of the mascot square, for the blink animation
  flowbit-logo.png     the ghost alone, for the app header
  flowbit_wordmark.png the name, used nowhere in the app's logo any more

Call these only after the QApplication exists (QPixmap needs it); results are cached.
"""
import json
from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QPixmap

ASSETS = Path(__file__).resolve().parent.parent / "assets"


@lru_cache(maxsize=None)
def mascot_pixmap() -> QPixmap | None:
    pm = QPixmap(str(ASSETS / "flowbit-mascot.png"))
    return None if pm.isNull() else pm


@lru_cache(maxsize=None)
def logo_pixmap() -> QPixmap | None:
    pm = QPixmap(str(ASSETS / "flowbit-logo.png"))
    return None if pm.isNull() else pm


@lru_cache(maxsize=None)
def mascot_eyes() -> tuple[tuple[float, float, float, float], ...]:
    """Eye boxes (x0, y0, x1, y1) as fractions of the mascot square; empty if the file is missing (no blinking)."""
    f = ASSETS / "flowbit-mascot.json"
    if not f.exists():
        return ()
    return tuple(tuple(e) for e in json.loads(f.read_text(encoding="utf-8"))["eyes"])
