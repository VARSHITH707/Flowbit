"""VoiceType. Everything it writes stays inside its own folder (APP_DIR), including temporary files."""
import sys
import tempfile
from pathlib import Path

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
(APP_DIR / ".tmp").mkdir(exist_ok=True)
tempfile.tempdir = str(APP_DIR / ".tmp")
