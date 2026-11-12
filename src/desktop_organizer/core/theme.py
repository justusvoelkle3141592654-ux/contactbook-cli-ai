"""Design tokens and the application style sheet (see docs/design-system.md)."""

from __future__ import annotations

from dataclasses import dataclass, fields

FONT_FAMILIES = ("Segoe UI Variable Text", "Segoe UI", "Inter")


@dataclass(frozen=True)
class Tokens:
    window: str
    surface: str
    surface_alt: str
    surface_pressed: str
    divider: str
    control_border: str
    text: str
    text_secondary: str
    text_disabled: str
    accent: str
    accent_hover: str
    accent_pressed: str
    on_accent: str
    selection: str
    success: str
    warning: str
    error: str
    on_error: str


LIGHT = Tokens(
    window="#F5F5F5",
    surface="#FFFFFF",
    surface_alt="#EDEDED",
    surface_pressed="#E3E3E3",
    divider="#E3E3E3",
    control_border="#8F8F8F",
    text="#1B1B1B",
    text_secondary="#5E5E5E",
    text_disabled="#9E9E9E",
    accent="#1F5FBF",
    accent_hover="#1A52A6",
    accent_pressed="#15458C",
    on_accent="#FFFFFF",
    selection="#DCE6F5",
    success="#1E7A3C",
    warning="#8A5A00",
    error="#C42B1C",
    on_error="#FFFFFF",
)

DARK = Tokens(
    window="#1C1C1C",
    surface="#262626",
    surface_alt="#303030",
    surface_pressed="#383838",
    divider="#353535",
    control_border="#7A7A7A",
    text="#F0F0F0",
    text_secondary="#ADADAD",
    text_disabled="#727272",
    accent="#6CA6EE",
    accent_hover="#86B6F2",
    accent_pressed="#5A93DB",
    on_accent="#0E1A2B",
    selection="#2A3A52",
    success="#62C281",
    warning="#E2B252",
    error="#FF8F85",
    on_error="#2B0E0B",
)


def tokens_for(dark: bool) -> Tokens:
    return DARK if dark else LIGHT


def token_names() -> list[str]:
    return [f.name for f in fields(Tokens)]


def build_stylesheet(t: Tokens) -> str:
    families = ", ".join(f'"{name}"' for name in FONT_FAMILIES)
    return f"""
* {{
    font-family: {families};
    font-size: 14px;
}}
QWidget {{
    color: {t.text};
}}
QMainWindow, QDialog, QWidget#ToolRoot {{
    background: {t.window};
}}
QLabel {{
    background: transparent;
}}
QLabel[textStyle="caption"] {{ font-size: 12px; color: {t.text_secondary}; }}
QLabel[textStyle="group"] {{ font-size: 12px; font-weight: 600; color: {t.text_secondary}; }}
QLabel[textStyle="subtitle"] {{ font-size: 16px; font-weight: 600; }}
QLabel[textStyle="title"] {{ font-size: 20px; font-weight: 600; }}
QLabel[textStyle="secondary"] {{ color: {t.text_secondary}; }}
QLabel[textStyle="empty"] {{ color: {t.text_secondary}; padding: 24px; }}

QPushButton {{
    background: {t.surface};
    border: 1px solid {t.control_border};
    border-radius: 4px;
    min-height: 30px;
    padding: 0 15px;
}}
QPushButton:hover {{ background: {t.surface_alt}; }}
QPushButton:pressed {{ background: {t.surface_pressed}; }}
QPushButton:focus {{ border: 2px solid {t.accent}; padding: 0 14px; min-height: 28px; }}
QPushButton:disabled {{ color: {t.text_disabled}; border-color: {t.divider}; }}
QPushButton[role="primary"] {{
    background: {t.accent}; color: {t.on_accent}; border: 1px solid {t.accent};
}}
QPushButton[role="primary"]:hover {{
    background: {t.accent_hover}; border-color: {t.accent_hover};
}}
QPushButton[role="primary"]:pressed {{ background: {t.accent_pressed}; }}
QPushButton[role="primary"]:focus {{ border: 2px solid {t.text}; }}
QPushButton[role="destructive"] {{
    background: {t.error}; color: {t.on_error}; border: 1px solid {t.error};
}}
QPushButton[role="destructive"]:focus {{ border: 2px solid {t.text}; }}

QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
    background: {t.surface};
    border: 1px solid {t.control_border};
    border-radius: 4px;
    min-height: 30px;
    padding: 0 8px;
    selection-background-color: {t.accent};
    selection-color: {t.on_accent};
}}
QPlainTextEdit, QTextEdit {{ padding: 6px 8px; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {t.control_border};
    border-bottom: 2px solid {t.accent};
}}
QLineEdit:disabled, QComboBox:disabled {{ color: {t.text_disabled}; border-color: {t.divider}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {t.surface};
    border: 1px solid {t.control_border};
    selection-background-color: {t.selection};
    selection-color: {t.text};
    outline: none;
}}

QListView, QTreeView, QTableView {{
    background: {t.surface};
    border: 1px solid {t.divider};
    border-radius: 4px;
    outline: none;
}}
QHeaderView::section {{
    background: {t.surface_alt};
    border: none;
    border-bottom: 1px solid {t.divider};
    padding: 6px 8px;
    font-size: 12px;
    font-weight: 600;
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {t.control_border}; border-radius: 3px; min-height: 32px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: {t.control_border}; border-radius: 3px; min-width: 32px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QFrame#Divider {{ background: {t.divider}; max-height: 1px; min-height: 1px; border: none; }}
QWidget#StatusLine {{ background: {t.window}; border-top: 1px solid {t.divider}; }}

QToolTip {{
    background: {t.surface};
    color: {t.text};
    border: 1px solid {t.control_border};
    padding: 4px 8px;
}}
"""
