import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # UI tests must not pop windows onto the desktop


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """Every test gets its own settings/history/memory folder; nothing touches the real userdata folder."""
    monkeypatch.setenv("VOICETYPE_HOME", str(tmp_path))


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
