from PySide6.QtWidgets import QMainWindow, QTabWidget

from .history_page import HistoryPage
from .home_page import HomePage
from .memory_page import MemoryPage
from .models_page import ModelsPage
from .settings_page import SettingsPage

TABS = ("home", "history", "memory", "models", "settings")


class MainWindow(QMainWindow):
    def __init__(self, cfg_holder, history, transcriber):
        super().__init__()
        self.setWindowTitle("Flowbit")
        self.resize(760, 640)
        self.home = HomePage(cfg_holder)
        self.history = HistoryPage(history)
        self.memory = MemoryPage()
        self.models = ModelsPage(cfg_holder, transcriber)
        self.settings = SettingsPage(cfg_holder)
        self.tabs = QTabWidget()
        for page, name in zip((self.home, self.history, self.memory, self.models, self.settings), ("Home", "History", "Memory", "Models", "Settings")):
            self.tabs.addTab(page, name)
        self.setCentralWidget(self.tabs)
        self.home.open_tab.connect(self.show_tab)
        refresh = {1: self.history.refresh, 2: self.memory.refresh, 3: self.models.refresh}
        self.tabs.currentChanged.connect(lambda i: refresh.get(i, lambda: None)())
        self.quitting = False

    def show_tab(self, name: str):
        self.tabs.setCurrentIndex(TABS.index(name) if name in TABS else 0)
        if name == "settings" and self.home.err_msg.text().lower().find("microphone") >= 0:
            self.settings.focus_mic()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        if self.quitting:
            e.accept()
        else:  # keep running in the tray so hotkeys keep working
            e.ignore()
            self.hide()
