"""
Vizier visual theme â€” **midnight indigo**, **antique gold**, **crimson**,
and a thread of **turquoise**.

The identity is original: a desert-palace mood rather than a copy of any
film.  The display face is the SIL OFL Rakkas font, bundled under
``assets/fonts`` and applied by :mod:`vizier.ui.branding`.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from vizier.ui.branding import (
    CRIMSON,
    CRIMSON_BRIGHT,
    CRIMSON_DEEP,
    GOLD,
    GOLD_BRIGHT,
    GOLD_DEEP,
    GOLD_PALE,
    INK,
    INK_DEEP,
    INK_SOFT,
    IVORY,
    IVORY_DIM,
    IVORY_MUTED,
    SURFACE,
    SURFACE_RAISED,
    TURQUOISE,
    load_display_font,
)

# ---------------------------------------------------------------------------
# Named colour palette
# ---------------------------------------------------------------------------

class Palette:
    """Central colour palette â€” all colours derived from the royal theme."""

    BACKGROUND = QColor(INK)
    BACKGROUND_DEEP = QColor(INK_DEEP)
    SURFACE = QColor(SURFACE)
    SURFACE_RAISED = QColor(SURFACE_RAISED)

    GOLD = QColor(GOLD)
    GOLD_BRIGHT = QColor(GOLD_BRIGHT)
    GOLD_DEEP = QColor(GOLD_DEEP)

    RED_DARK = QColor(CRIMSON_DEEP)
    RED = QColor(CRIMSON)
    RED_LIGHT = QColor(CRIMSON_BRIGHT)
    RED_BRIGHT = QColor(CRIMSON_BRIGHT)

    TURQUOISE = QColor(TURQUOISE)
    WHITE = QColor(IVORY)
    WHITE_DIM = QColor(IVORY_DIM)
    GREY_DARK = QColor(INK_SOFT)
    GREY = QColor(IVORY_MUTED)
    GREY_LIGHT = QColor("#9C94AE")
    GREEN = QColor(TURQUOISE)
    ORANGE = QColor(GOLD_BRIGHT)

    @classmethod
    def background_hex(cls) -> str:
        return INK

    @classmethod
    def red_hex(cls) -> str:
        return CRIMSON


PALETTE = Palette()

# Convenience constants for non-Qt code (console, HTML, etc.)
COLORS_BG = INK
COLORS_RED = CRIMSON
COLORS_RED_BRIGHT = CRIMSON_BRIGHT
COLORS_WHITE = IVORY
COLORS_WHITE_DIM = IVORY_DIM
COLORS_GREEN = TURQUOISE
COLORS_ORANGE = GOLD
COLORS_GREY = IVORY_MUTED
COLORS_GOLD = GOLD
COLORS_TURQUOISE = TURQUOISE
COLORS_SURFACE = SURFACE


def setup_theme(app: QApplication) -> None:
    """Apply the Vizier theme (palette + fonts + stylesheet) to a QApplication."""
    app.setStyle("Fusion")
    load_display_font()

    font = QFont("Segoe UI", 9)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, PALETTE.BACKGROUND)
    palette.setColor(QPalette.ColorRole.WindowText, PALETTE.WHITE)
    palette.setColor(QPalette.ColorRole.Base, QColor(INK_SOFT))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(INK))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(SURFACE_RAISED))
    palette.setColor(QPalette.ColorRole.ToolTipText, PALETTE.WHITE)
    palette.setColor(QPalette.ColorRole.Text, PALETTE.WHITE)
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(IVORY_MUTED))
    palette.setColor(QPalette.ColorRole.Button, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.ButtonText, PALETTE.WHITE)
    palette.setColor(QPalette.ColorRole.BrightText, QColor(GOLD_BRIGHT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(CRIMSON))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(IVORY))
    palette.setColor(QPalette.ColorRole.Link, QColor(GOLD_BRIGHT))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor(TURQUOISE))
    palette.setColor(QPalette.ColorRole.Light, QColor(SURFACE_RAISED))
    palette.setColor(QPalette.ColorRole.Mid, QColor(INK_SOFT))
    palette.setColor(QPalette.ColorRole.Dark, QColor(INK_DEEP))
    palette.setColor(QPalette.ColorRole.Shadow, QColor(INK_DEEP))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)


# ---------------------------------------------------------------------------
# The stylesheet (QSS) â€” midnight palace
# ---------------------------------------------------------------------------

STYLESHEET = f"""
/* ===== Vizier Royal Theme: Midnight / Antique Gold / Crimson ===== */

QWidget {{
    color: {IVORY};
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 9pt;
}}

QMainWindow, QDialog {{
    background-color: {INK};
}}

QLabel {{
    background: transparent;
    color: {IVORY};
}}

QLabel#Eyebrow {{
    color: {GOLD};
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 3px;
}}

QLabel#SectionTitle {{
    color: {IVORY};
    font-size: 14pt;
    font-weight: 600;
}}

QLabel#ChatTitle {{
    color: {IVORY};
    font-size: 13pt;
    font-weight: 600;
}}

QLabel#Badge {{
    color: {TURQUOISE};
    border: 1px solid rgba(79, 209, 197, 95);
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 1px;
    background: rgba(79, 209, 197, 16);
}}

QLabel#DropHint {{
    color: {GOLD};
    border: 1px dashed rgba(212, 168, 87, 120);
    border-radius: 8px;
    padding: 10px;
    background: rgba(212, 168, 87, 10);
}}

QLabel#Hint, QLabel.dim {{
    color: {IVORY_MUTED};
}}

QLabel.red {{
    color: {CRIMSON_BRIGHT};
    font-weight: bold;
}}

QLabel.red-bright {{
    color: {CRIMSON_BRIGHT};
}}

QStatusBar {{
    background-color: {INK_DEEP};
    color: {IVORY_DIM};
    border-top: 1px solid rgba(212, 168, 87, 55);
    padding: 3px 12px;
}}

QStatusBar QLabel {{
    color: {IVORY_MUTED};
}}

QLabel#VersionLabel {{
    color: {GOLD};
    font-size: 8pt;
    letter-spacing: 1px;
    padding-right: 10px;
}}

/* ---------- Sidebar / chat surfaces ---------- */

QWidget#Sidebar {{
    background: rgba(11, 9, 24, 175);
    border-right: 1px solid rgba(212, 168, 87, 48);
}}

QWidget#ChatArea {{
    background: transparent;
}}

QScrollArea {{
    background: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

QWidget#ChatHeader {{
    background: rgba(12, 10, 25, 185);
    border-bottom: 1px solid rgba(212, 168, 87, 55);
}}

QTextEdit#ChatDisplay {{
    background: rgba(8, 7, 17, 188);
    border: 1px solid rgba(212, 168, 87, 42);
    border-radius: 12px;
    padding: 14px;
    color: {IVORY};
    selection-background-color: {CRIMSON};
    selection-color: {IVORY};
}}

QWidget#InputBar {{
    background: rgba(10, 8, 21, 210);
    border-top: 1px solid rgba(212, 168, 87, 55);
}}

/* ---------- Buttons ---------- */

QPushButton {{
    background-color: rgba(26, 22, 47, 235);
    border: 1px solid rgba(92, 82, 128, 220);
    border-radius: 8px;
    padding: 6px 14px;
    color: {IVORY};
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: rgba(36, 30, 62, 240);
    border: 1px solid {GOLD};
    color: {GOLD_PALE};
}}

QPushButton:pressed {{
    background-color: {INK_DEEP};
    border: 1px solid {GOLD_DEEP};
}}

QPushButton:focus {{
    border: 1px solid {GOLD_BRIGHT};
}}

QPushButton:disabled {{
    color: {IVORY_MUTED};
    border: 1px solid rgba(70, 64, 92, 150);
    background-color: rgba(20, 17, 34, 150);
}}

QPushButton.flat {{
    background: transparent;
    border: none;
}}

QPushButton.danger {{
    background-color: rgba(92, 15, 29, 150);
    border: 1px solid rgba(200, 50, 74, 160);
    color: #F0A8B2;
}}

QPushButton.danger:hover {{
    background-color: rgba(142, 27, 44, 210);
    border: 1px solid {CRIMSON_BRIGHT};
    color: {IVORY};
}}

QPushButton.accent, QPushButton.primary {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #F0D391, stop:0.38 #E2BE77, stop:0.72 #C89A4B, stop:1 #A97C33);
    border: 1px solid {GOLD_BRIGHT};
    border-radius: 8px;
    color: #1C1305;
    font-weight: 700;
    padding: 7px 18px;
}}

QPushButton.accent:hover, QPushButton.primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FBE8B7, stop:0.40 #F0D391, stop:0.75 #D9AC5C, stop:1 #BC8C3C);
    border: 1px solid #FFF1CC;
    color: #150E02;
}}

QPushButton.accent:pressed, QPushButton.primary:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #C89A4B, stop:1 #8C6A2A);
    border: 1px solid {GOLD_DEEP};
    color: #120C02;
}}

QPushButton.accent:disabled, QPushButton.primary:disabled {{
    background: rgba(120, 96, 52, 120);
    border: 1px solid rgba(140, 106, 42, 130);
    color: rgba(245, 239, 226, 120);
}}

QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    color: {IVORY};
    padding: 4px;
}}

QToolButton:hover {{
    background: rgba(212, 168, 87, 24);
    border: 1px solid rgba(212, 168, 87, 90);
}}

/* ---------- Inputs ---------- */

QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: rgba(9, 8, 19, 205);
    border: 1px solid rgba(74, 66, 104, 210);
    border-radius: 8px;
    padding: 5px 8px;
    color: {IVORY};
    selection-background-color: {CRIMSON};
    selection-color: {IVORY};
    placeholder-text-color: {IVORY_MUTED};
}}

QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{
    border: 1px solid rgba(110, 98, 148, 220);
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {GOLD};
    background-color: rgba(13, 11, 26, 225);
}}

QComboBox {{
    background-color: rgba(24, 20, 43, 235);
    border: 1px solid rgba(74, 66, 104, 210);
    border-radius: 8px;
    padding: 5px 8px;
    color: {IVORY};
}}

QComboBox:hover, QComboBox:focus {{
    border: 1px solid {GOLD};
}}

QComboBox::drop-down {{
    border: 0px;
    background: transparent;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: {INK_SOFT};
    border: 1px solid {GOLD_DEEP};
    color: {IVORY};
    selection-background-color: {CRIMSON};
    selection-color: {IVORY};
    outline: none;
}}

QSpinBox, QDoubleSpinBox {{
    background-color: rgba(9, 8, 19, 205);
    border: 1px solid rgba(74, 66, 104, 210);
    border-radius: 8px;
    padding: 4px 6px;
    color: {IVORY};
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {GOLD};
}}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background-color: rgba(32, 27, 56, 230);
    border-left: 1px solid rgba(74, 66, 104, 160);
    width: 15px;
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: rgba(212, 168, 87, 60);
}}

QCheckBox, QRadioButton {{
    color: {IVORY};
    spacing: 8px;
    background: transparent;
}}

QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid rgba(120, 106, 160, 220);
    border-radius: 4px;
    background-color: rgba(12, 10, 24, 210);
}}

QCheckBox::indicator:hover {{
    border: 1px solid {GOLD};
}}

QCheckBox::indicator:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {GOLD_BRIGHT}, stop:1 {GOLD});
    border: 1px solid {GOLD_PALE};
}}

QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid rgba(120, 106, 160, 220);
    border-radius: 8px;
    background-color: rgba(12, 10, 24, 210);
}}

QRadioButton::indicator:checked {{
    background-color: {GOLD};
    border: 2px solid {GOLD_BRIGHT};
}}

/* ---------- Menus ---------- */

QMenuBar {{
    background-color: {INK_DEEP};
    color: {IVORY_DIM};
    border-bottom: 1px solid rgba(212, 168, 87, 38);
    padding: 2px 8px;
    spacing: 4px;
}}

QMenuBar::item {{
    background: transparent;
    padding: 5px 10px;
    border-radius: 5px;
}}

QMenuBar::item:selected {{
    background: rgba(212, 168, 87, 24);
    color: {GOLD_BRIGHT};
}}

QMenu {{
    background-color: {SURFACE};
    color: {IVORY};
    border: 1px solid rgba(212, 168, 87, 110);
    border-radius: 8px;
    padding: 6px;
}}

QMenu::item {{
    padding: 6px 22px 6px 18px;
    border-radius: 5px;
}}

QMenu::item:selected {{
    background: rgba(142, 27, 44, 170);
    color: {IVORY};
}}

QMenu::item:disabled {{
    color: {IVORY_MUTED};
}}

QMenu::separator {{
    height: 1px;
    background: rgba(212, 168, 87, 40);
    margin: 5px 8px;
}}

QToolBar {{
    background-color: {INK_DEEP};
    border: 0px;
    border-bottom: 1px solid rgba(212, 168, 87, 55);
    spacing: 6px;
    padding: 3px;
}}

QToolBar::separator {{
    border-right: 1px solid rgba(212, 168, 87, 50);
    margin: 4px;
}}

/* ---------- Lists and tables ---------- */

QListWidget, QListView, QTreeView, QTreeWidget, QTableWidget {{
    background-color: rgba(10, 8, 20, 170);
    border: 1px solid rgba(74, 66, 104, 170);
    border-radius: 8px;
    color: {IVORY};
    outline: none;
    alternate-background-color: rgba(24, 20, 43, 120);
}}

QListWidget::item, QListView::item, QTreeView::item {{
    padding: 5px 7px;
    border-radius: 5px;
}}

QListWidget::item:hover, QTreeView::item:hover {{
    background: rgba(212, 168, 87, 20);
}}

QListWidget::item:selected, QListView::item:selected,
QTreeView::item:selected, QTableWidget::item:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(142, 27, 44, 210), stop:1 rgba(92, 15, 29, 190));
    color: {IVORY};
}}

QTableWidget {{
    gridline-color: rgba(74, 66, 104, 90);
}}

QTableWidget::item {{
    padding: 5px;
}}

QHeaderView::section {{
    background-color: rgba(31, 26, 56, 235);
    color: {GOLD};
    border: none;
    border-right: 1px solid rgba(74, 66, 104, 120);
    border-bottom: 1px solid rgba(212, 168, 87, 60);
    padding: 6px 8px;
    font-weight: 600;
    letter-spacing: 1px;
}}

QTableCornerButton::section {{
    background-color: rgba(31, 26, 56, 235);
    border: none;
}}

/* ---------- Scroll bars ---------- */

QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: rgba(120, 106, 160, 120);
    min-height: 30px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: rgba(212, 168, 87, 180);
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: transparent;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: rgba(120, 106, 160, 120);
    min-width: 30px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background: rgba(212, 168, 87, 180);
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: transparent;
}}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

/* ---------- Tabs ---------- */

QTabWidget::pane {{
    border: 1px solid rgba(212, 168, 87, 70);
    border-radius: 10px;
    background: rgba(10, 8, 20, 110);
    top: -1px;
}}

QTabBar::tab {{
    background-color: rgba(24, 20, 43, 210);
    color: {IVORY_DIM};
    border: 1px solid rgba(74, 66, 104, 160);
    border-bottom: none;
    padding: 7px 18px;
    margin-right: 3px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}}

QTabBar::tab:hover {{
    background-color: rgba(36, 30, 62, 230);
    color: {GOLD_BRIGHT};
}}

QTabBar::tab:selected {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(142, 27, 44, 230), stop:1 rgba(92, 15, 29, 220));
    color: {IVORY};
    border: 1px solid rgba(212, 168, 87, 130);
    border-bottom: none;
    font-weight: 600;
}}

/* ---------- Group boxes ---------- */

QGroupBox {{
    background: rgba(18, 15, 33, 130);
    border: 1px solid rgba(212, 168, 87, 45);
    border-radius: 10px;
    margin-top: 16px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
    color: {GOLD_BRIGHT};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {GOLD};
    background: transparent;
    letter-spacing: 1px;
}}

/* ---------- Progress / splitters ---------- */

QProgressBar {{
    border: 1px solid rgba(74, 66, 104, 170);
    border-radius: 6px;
    background-color: rgba(8, 7, 17, 200);
    text-align: center;
    color: {IVORY_DIM};
    min-height: 12px;
}}

QProgressBar::chunk {{
    border-radius: 5px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {GOLD_DEEP}, stop:0.45 {GOLD}, stop:1 {GOLD_BRIGHT});
}}

QSplitter::handle {{
    background: transparent;
}}

QSplitter::handle:horizontal {{
    width: 3px;
}}

QSplitter::handle:hover {{
    background: rgba(212, 168, 87, 90);
}}

/* ---------- Chat markup (also used by the inline renderer) ---------- */

.user-message {{
    background-color: rgba(21, 18, 40, 220);
    border-left: 3px solid {CRIMSON_BRIGHT};
    border-radius: 6px;
    padding: 10px 12px;
    margin: 6px 0;
}}

.assistant-message {{
    background-color: rgba(12, 10, 24, 210);
    border-left: 3px solid {GOLD};
    border-radius: 6px;
    padding: 10px 12px;
    margin: 6px 0;
}}

.tool-result {{
    background-color: rgba(8, 7, 17, 200);
    border: 1px solid rgba(74, 66, 104, 170);
    border-radius: 6px;
    padding: 6px 10px;
    font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
    font-size: 8pt;
    color: {IVORY_DIM};
}}

/* ---------- Drop zone / misc ---------- */

QDropZone {{
    background-color: rgba(10, 8, 20, 160);
    border: 2px dashed rgba(212, 168, 87, 130);
    border-radius: 10px;
    padding: 20px;
    color: {GOLD};
}}

QDropZone.dragover {{
    border-color: {GOLD_BRIGHT};
    background-color: rgba(212, 168, 87, 26);
}}

QToolTip {{
    background-color: {SURFACE};
    color: {IVORY};
    border: 1px solid {GOLD_DEEP};
    border-radius: 5px;
    padding: 5px 8px;
}}

QDialogButtonBox::button {{
    min-width: 84px;
}}

QInputDialog QLabel, QMessageBox QLabel {{
    color: {IVORY};
}}
"""

