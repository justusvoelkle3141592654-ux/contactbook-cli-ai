"""Mockup of the file cleaner window for design review.

Not part of the application. It uses the real ToolWindow base class, widgets and style
sheet with sample data, so the review shows what the shipped tool will look like.
Sample strings are German on purpose; the real tool uses the language files.

Run: QT_QPA_PLATFORM=offscreen python docs/mockups/file_cleaner_mockup.py out.png [light|dark]
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

ROWS = [
    ("Rechnung_2026-10.pdf", "Dokument", "Dokumente", "184 KB"),
    ("IMG_4021.jpg", "Bild", "Bilder", "3,2 MB"),
    ("IMG_4022.jpg", "Bild", "Bilder", "3,1 MB"),
    ("Präsentation Q3.pptx", "Präsentation", "Dokumente", "6,8 MB"),
    ("setup-tool-2.4.1.exe", "Programm", "Programme", "48,0 MB"),
    ("Urlaub Kroatien.mp4", "Video", "Videos", "812 MB"),
    ("daten-export.csv", "Tabelle", "Tabellen", "92 KB"),
    ("Projektplan.xlsx", "Tabelle", "Tabellen", "41 KB"),
    ("archiv_alt.zip", "Archiv", "Archive", "220 MB"),
    ("Sprachmemo 12.m4a", "Audio", "Audio", "1,4 MB"),
    ("notizen.txt", "Text", "Dokumente", "3 KB"),
]


def main() -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QComboBox,
        QHeaderView,
        QLabel,
        QLineEdit,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
    )

    from desktop_organizer.app.context import AppContext
    from desktop_organizer.app.theming import ThemeManager
    from desktop_organizer.app.tool_window import ToolWindow
    from desktop_organizer.core.i18n import Translator, install
    from desktop_organizer.core.paths import AppPaths, resources_dir
    from desktop_organizer.core.settings import Settings
    from desktop_organizer.core.storage import Database

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("file-cleaner.png")
    mode = sys.argv[2] if len(sys.argv) > 2 else "light"
    app = QApplication(sys.argv[:1])
    paths = AppPaths(Path(tempfile.mkdtemp()) / "data", portable=False)
    paths.ensure()
    settings = Settings(paths.settings_file)
    settings.load()
    translator = Translator(resources_dir() / "i18n", "de")
    install(translator)
    theme = ThemeManager(app, mode)
    context = AppContext(paths, settings, translator, Database(paths.database_file), theme, "")

    class FileCleanerMockup(ToolWindow):
        tool_id = "file_cleaner"
        icon = "folder-tree"

    window = FileCleanerMockup(context)

    folder = QLineEdit("C:\\Users\\anna\\Downloads")
    folder.setReadOnly(True)
    choose = QPushButton("Ordner wählen …")
    scan = QPushButton("Vorschau erstellen")
    window.toolbar.addWidget(folder, 1)
    window.toolbar.addWidget(choose)
    window.toolbar.addWidget(scan)

    summary = QLabel("11 Dateien  ·  7 Zielordner  ·  1,1 GB  ·  Nichts wird gelöscht")
    summary.setProperty("textStyle", "secondary")
    filter_box = QComboBox()
    filter_box.addItems(["Alle Typen", "Bilder", "Dokumente", "Videos"])
    filter_box.setMinimumWidth(180)
    from PySide6.QtWidgets import QHBoxLayout

    summary_row = QHBoxLayout()
    summary_row.addWidget(summary, 1)
    summary_row.addWidget(filter_box)
    window.content.addLayout(summary_row)

    table = QTableWidget(len(ROWS), 4)
    table.setHorizontalHeaderLabels(["Datei", "Typ", "Ziel", "Größe"])
    table.verticalHeader().setVisible(False)
    table.setShowGrid(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    header.setHighlightSections(False)
    for row, values in enumerate(ROWS):
        for col, value in enumerate(values):
            item = QTableWidgetItem(value if col != 2 else f"{value}\\")
            if col == 0:
                item.setIcon(theme.icon("file-text", secondary=True))
            if col == 3:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, col, item)
        table.setRowHeight(row, 40)
    table.setColumnWidth(1, 140)
    table.setColumnWidth(2, 160)
    table.setColumnWidth(3, 110)
    table.selectRow(5)
    window.content.addWidget(table, 1)

    hint = QLabel("Die Verschiebung lässt sich danach mit einem Klick rückgängig machen.")
    hint.setProperty("textStyle", "caption")
    undo = QPushButton("Letzten Lauf rückgängig machen")
    undo.setEnabled(False)
    move = QPushButton("11 Dateien verschieben")
    move.setProperty("role", "primary")
    window.footer.addWidget(hint, 1)
    window.footer.addWidget(undo)
    window.footer.addWidget(move)

    window.resize(1000, 680)
    window.show()
    app.processEvents()
    window.grab().save(str(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
