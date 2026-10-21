"""Flowbit brand images: the approved mascot and wordmark, cut from the logo by scripts/make_brand_assets.py.

The PNGs live in voicetype/assets and are committed, so the app needs no image from the internet at run time.
Call these only after the QApplication exists (QPixmap needs it); results are cached.
"""
from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QPixmap

ASSETS = Path(__file__).resolve().parent.parent / "assets"


@lru_cache(maxsize=None)
def mascot_pixmap() -> QPixmap | None:
    pm = QPixmap(str(ASSETS / "flowbit_mascot.png"))
    return None if pm.isNull() else pm


@lru_cache(maxsize=None)
def wordmark_pixmap() -> QPixmap | None:
    pm = QPixmap(str(ASSETS / "flowbit_wordmark.png"))
    return None if pm.isNull() else pm
