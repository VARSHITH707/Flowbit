"""Flowbit theme: black and orange (dark, the brand default), a light variant, or follow Windows."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

BRAND = dict(black="#0B0B0B", orange="#FF7900", white="#F5F5F5")
PALETTES = {
    "dark": dict(bg=BRAND["black"], panel="#151515", text=BRAND["white"], muted="#a8a8a8", accent=BRAND["orange"],
                 border="#2a2a2a", good="#3ecf8e", bad="#ff5c5c", warn="#ffb547", input="#1c1c1c", on_accent="#0B0B0B"),
    "light": dict(bg="#fafafa", panel="#ffffff", text="#141414", muted="#5c5c5c", accent="#b35000", border="#dadada",
                  good="#0f8a4f", bad="#c62828", warn="#9a5b00", input="#ffffff", on_accent="#ffffff"),
}

_QSS = """
* {{ font-family: 'Segoe UI', sans-serif; font-size: 10pt; }}
QWidget {{ background: {bg}; color: {text}; }}
QMainWindow, QDialog {{ background: {bg}; }}
QLabel, QCheckBox {{ background: transparent; }}
QTabWidget::pane {{ border: 1px solid {border}; background: {bg}; top: -1px; }}
QTabBar::tab {{ background: {panel}; color: {muted}; padding: 8px 18px; border: 1px solid {border}; border-bottom: none; }}
QTabBar::tab:selected {{ color: {text}; background: {bg}; border-bottom: 2px solid {accent}; }}
QTabBar::tab:focus {{ outline: 1px solid {accent}; }}
QGroupBox {{ border: 1px solid {border}; border-radius: 6px; margin-top: 14px; padding: 12px 8px 8px 8px; background: {panel}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {muted}; background: {panel}; }}
QGroupBox QWidget {{ background: transparent; }}
QPushButton {{ background: {panel}; border: 1px solid {border}; border-radius: 5px; padding: 6px 14px; }}
QPushButton:hover {{ border-color: {accent}; }}
QPushButton:focus {{ border: 2px solid {accent}; }}
QPushButton:disabled {{ color: {muted}; }}
QPushButton#primary {{ background: {accent}; color: {on_accent}; border: none; font-weight: 600; }}
QPushButton#primary:disabled {{ background: {border}; color: {muted}; }}
QPushButton#danger {{ color: {bad}; }}
QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit, QListWidget, QTableWidget {{
    background: {input}; border: 1px solid {border}; border-radius: 4px; padding: 4px; selection-background-color: {accent}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus, QListWidget:focus, QTableWidget:focus {{ border: 2px solid {accent}; }}
QHeaderView::section {{ background: {panel}; color: {muted}; border: none; border-bottom: 1px solid {border}; padding: 4px; }}
QProgressBar {{ border: 1px solid {border}; border-radius: 4px; text-align: center; background: {input}; }}
QProgressBar::chunk {{ background: {accent}; }}
QLabel#muted {{ color: {muted}; }}
QLabel#title {{ font-size: 15pt; font-weight: 600; }}
QLabel#error {{ color: {bad}; }}
QFrame#card {{ background: {panel}; border: 1px solid {border}; border-radius: 8px; }}
QFrame#errorcard {{ background: {panel}; border: 1px solid {bad}; border-radius: 8px; }}
QCheckBox:focus {{ outline: 1px solid {accent}; }}
"""


def resolve(theme: str) -> str:
    if theme in PALETTES:
        return theme
    scheme = QGuiApplication.styleHints().colorScheme()
    return "light" if scheme == Qt.ColorScheme.Light else "dark"


def colors(theme: str) -> dict:
    return PALETTES[resolve(theme)]


def apply_theme(app, theme: str) -> None:
    app.setStyleSheet(_QSS.format(**colors(theme)))
