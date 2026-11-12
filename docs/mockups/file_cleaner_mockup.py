"""Static mockup of the file cleaner window for design review.

Not part of the application. It uses the real style sheet and the shared tool window
layout with sample data, so the review shows exactly what the shipped tool will look like.
Strings are German sample text on purpose; the real tool uses the language files.

Run: python docs/mockups/file_cleaner_mockup.py <output.png> [light|dark]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

ROWS = [
    ("Rechnung_2026-10.pdf", "Dokumente", "Dokumente\\", "184 KB"),
    ("IMG_4021.jpg", "Bilder", "Bilder\\", "3,2 MB"),
    ("IMG_4022.jpg", "Bilder", "Bilder\\", "3,1 MB"),
    ("Präsentation Q3.pptx", "Dokumente", "Dokumente\\", "6,8 MB"),
    ("setup-tool-2.4.1.exe", "Programme", "Programme\\", "48,0 MB"),
    ("Urlaub Kroatien.mp4", "Videos", "Videos\\", "812 MB"),
    ("daten-export.csv", "Tabellen", "Tabellen\\", "92 KB"),
    ("Projektplan.xlsx", "Tabellen", "Tabellen\\", "41 KB"),
    ("archiv_alt.zip", "Archive", "Archive\\", "220 MB"),
    ("Sprachmemo 12.m4a", "Audio", "Audio\\", "1,4 MB"),
    ("notizen.txt", "Dokumente", "Dokumente\\", "3 KB"),
]


def build() -> QWidget:
    window = QWidget()
    window.setObjectName("ToolRoot")
    window.setWindowTitle("Dateiaufräumer – Desktop Organizer")
    window.resize(880, 600)

    from PySide6.QtWidgets import QVBoxLayout

    root = QVBoxLayout(window)
    root.setContentsMargins(16, 16, 16, 16)
    root.setSpacing(12)

    heading = QLabel("Dateiaufräumer")
    heading.setProperty("textStyle", "title")
    root.addWidget(heading)

    toolbar = QHBoxLayout()
    toolbar.setSpacing(8)
    folder = QLineEdit("C:\\Users\\anna\\Downloads")
    folder.setReadOnly(True)
    choose = QPushButton("Ordner wählen …")
    scan = QPushButton("Vorschau erstellen")
    toolbar.addWidget(folder, 1)
    toolbar.addWidget(choose)
    toolbar.addWidget(scan)
    root.addLayout(toolbar)

    summary = QLabel("11 von 11 Dateien werden in 7 Unterordner verschoben. Nichts wird gelöscht.")
    summary.setProperty("textStyle", "secondary")
    root.addWidget(summary)

    table = QTableWidget(len(ROWS), 4)
    table.setHorizontalHeaderLabels(["Datei", "Typ", "Ziel", "Größe"])
    table.verticalHeader().setVisible(False)
    table.setShowGrid(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setAlternatingRowColors(False)
    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    for row, values in enumerate(ROWS):
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col == 0:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
            if col == 3:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, col, item)
        table.setRowHeight(row, 36)
    table.setColumnWidth(1, 120)
    table.setColumnWidth(2, 160)
    table.setColumnWidth(3, 96)
    root.addWidget(table, 1)

    footer = QHBoxLayout()
    footer.setSpacing(8)
    progress = QProgressBar()
    progress.setVisible(False)
    undo = QPushButton("Letzten Lauf rückgängig machen")
    undo.setEnabled(False)
    move = QPushButton("Dateien verschieben")
    move.setProperty("role", "primary")
    footer.addWidget(progress, 1)
    footer.addStretch(1)
    footer.addWidget(undo)
    footer.addWidget(move)
    root.addLayout(footer)
    return window


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("file-cleaner.png")
    mode = sys.argv[2] if len(sys.argv) > 2 else "light"
    app = QApplication(sys.argv[:1])

    from desktop_organizer.app.theming import ThemeManager

    ThemeManager(app, mode)
    window = build()
    window.show()
    app.processEvents()
    window.grab().save(str(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
