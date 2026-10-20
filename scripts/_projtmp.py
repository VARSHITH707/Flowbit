"""Import first: keeps this script's temporary files in the project's .tmp folder instead of C:\\...\\Temp."""
import tempfile
from pathlib import Path

_dir = Path(__file__).resolve().parents[1] / ".tmp"
_dir.mkdir(exist_ok=True)
tempfile.tempdir = str(_dir)
