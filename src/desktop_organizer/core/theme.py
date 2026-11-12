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
    layer: str
    layer_border: str
    card: str
    card_hover: str
    card_border: str
    accent_subtle: str
    nav_hover: str
    nav_selected: str


LIGHT = Tokens(
    window="#F3F3F3",
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
    layer="#F9F9F9",
    layer_border="#E5E5E5",
    card="#FFFFFF",
    card_hover="#F6F6F6",
    card_border="#E3E3E3",
    accent_subtle="#E6EEFA",
    nav_hover="#EAEAEA",
    nav_selected="#E4E4E4",
)

DARK = Tokens(
    window="#1F1F1F",
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
    layer="#272727",
    layer_border="#1A1A1A",
    card="#2D2D2D",
    card_hover="#333333",
    card_border="#3A3A3A",
    accent_subtle="#24344B",
    nav_hover="#2D2D2D",
    nav_selected="#333333",
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
QMainWindow, QDialog {{
    background: {t.window};
}}
QWidget#ToolRoot {{
    background: {t.layer};
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
QLabel[textStyle="display"] {{ font-size: 28px; font-weight: 600; }}
QLabel[textStyle="section"] {{ font-size: 14px; font-weight: 600; }}
QLabel[textStyle="cardTitle"] {{ font-size: 14px; }}
QLabel[textStyle="appName"] {{ font-size: 14px; font-weight: 600; }}

QWidget#Sidebar {{ background: {t.window}; }}
QFrame#Layer {{
    background: {t.layer};
    border-top: 1px solid {t.layer_border};
    border-left: 1px solid {t.layer_border};
    border-top-left-radius: 8px;
}}
QWidget#PageBody, QScrollArea#PageScroll, QScrollArea#PageScroll > QWidget > QWidget {{
    background: transparent;
}}
QScrollArea#PageScroll {{ border: none; }}
QFrame#Card {{
    background: {t.card};
    border: 1px solid {t.card_border};
    border-radius: 8px;
}}
QLabel#IconTile {{ background: {t.accent_subtle}; border-radius: 6px; }}
QLabel#KeyHint {{
    color: {t.text_secondary};
    background: {t.layer};
    border: 1px solid {t.card_border};
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 12px;
}}
QPushButton[role="danger"] {{ color: {t.error}; }}

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
    background: {t.card};
    alternate-background-color: {t.card};
    border: 1px solid {t.card_border};
    border-radius: 8px;
    outline: none;
    selection-background-color: {t.selection};
    selection-color: {t.text};
}}
QTableView::item, QTreeView::item {{
    padding: 0 8px;
    border-bottom: 1px solid {t.divider};
}}
QTableView::item:hover, QTreeView::item:hover {{ background: {t.card_hover}; }}
QTableView::item:selected, QTreeView::item:selected {{
    background: {t.selection};
    color: {t.text};
}}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{
    background: {t.card};
    color: {t.text_secondary};
    border: none;
    border-bottom: 1px solid {t.card_border};
    padding: 8px;
    font-size: 12px;
    font-weight: 600;
}}
QTableCornerButton::section {{ background: {t.card}; border: none; }}
QProgressBar {{
    background: {t.nav_selected};
    border: none;
    border-radius: 2px;
    max-height: 4px;
    min-height: 4px;
    text-align: center;
}}
QProgressBar::chunk {{ background: {t.accent}; border-radius: 2px; }}

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
QWidget#StatusLine {{ background: {t.layer}; border-top: 1px solid {t.card_border}; }}

QToolTip {{
    background: {t.surface};
    color: {t.text};
    border: 1px solid {t.control_border};
    padding: 4px 8px;
}}
"""
