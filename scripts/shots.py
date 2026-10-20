"""Render the UI to PNGs (data/shots) for visual review. Uses a throwaway data folder."""
import os
import sys
import tempfile

import _projtmp  # noqa: F401  (temp files stay in the project)
from pathlib import Path

os.environ["VOICETYPE_HOME"] = tempfile.mkdtemp(prefix="vt_shots_home_")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtWidgets import QApplication

from voicetype.config import Config
from voicetype.history import History
from voicetype.transcriber import Transcriber
from voicetype.ui.main_window import MainWindow
from voicetype.ui.pill import StatePill
from voicetype.ui.setup_dialog import SetupDialog
from voicetype.ui.theme import apply_theme

app = QApplication(sys.argv[:1])
out = ROOT / "data" / "shots"
out.mkdir(parents=True, exist_ok=True)


class H:
    cfg = Config()


h = H()
hist = History()
for t in ("Hello team, the report is ready for review by Friday afternoon.", "Kubernetes and PostgreSQL are deployed.\nPlease check the logs."):
    hist.add(t, "en", 4.2, "large-v3-turbo")
for theme in ("dark", "light"):
    h.cfg.theme = theme
    apply_theme(app, theme)
    w = MainWindow(h, hist, Transcriber(lambda: h.cfg))
    w.resize(760, 640)
    w.show()
    w.home.set_transcript("Hello team, the report is ready for review by Friday.", "um hello team the report is ready for review by Thursday actually Friday")
    from voicetype import memory
    memory.learn([("cubernetes", "Kubernetes"), ("post gress", "Postgres"), ("send", "sent")])
    w.memory.refresh()
    from voicetype.ui.main_window import TABS
    for i, name in enumerate(TABS):
        w.tabs.setCurrentIndex(i)
        app.processEvents()
        w.grab().save(str(out / f"{theme}_{name}.png"))
    w.tabs.setCurrentIndex(0)
    w.home.on_state("failed", "Model 'large-v3-turbo' is not downloaded yet. Open the Models tab to download it.")
    app.processEvents()
    w.grab().save(str(out / f"{theme}_home_error.png"))
    w.close()
d = SetupDialog(h)
d.show()
for i in range(d.pages.count()):
    d.pages.setCurrentIndex(i)
    app.processEvents()
    d.grab().save(str(out / f"light_setup_{i}.png"))
d.close()
apply_theme(app, "dark")
p = StatePill()
for st, det in (("idle", ""), ("recording", ""), ("processing", ""), ("done", ""), ("failed", "Microphone unavailable")):
    p.set_state(st, det)
    app.processEvents()
    p.grab().save(str(out / f"pill_{st}.png"))
print("saved", sorted(x.name for x in out.iterdir()))
