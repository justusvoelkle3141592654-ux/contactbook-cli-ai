"""Render build/icon.svg into a multi-resolution Windows .ico (PNG-compressed entries).

Usage: python build/make_icon.py
Writes src/desktop_organizer/resources/app.ico.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "build" / "icon.svg"
TARGET = ROOT / "src" / "desktop_organizer" / "resources" / "app.ico"
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data.data())


def build_ico(images: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    payload = b""
    for size, png in images:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(payload))
        payload += png
    return header + entries + payload


def main() -> int:
    _app = QGuiApplication(sys.argv[:1])
    renderer = QSvgRenderer(str(SOURCE))
    if not renderer.isValid():
        print(f"Invalid SVG: {SOURCE}", file=sys.stderr)
        return 1
    images = [(size, render_png(renderer, size)) for size in SIZES]
    TARGET.write_bytes(build_ico(images))
    # 48 px bitmap shown at 24 logical pixels (2x) in the sidebar.
    (TARGET.parent / "app-24.png").write_bytes(render_png(renderer, 48))
    print(f"Wrote {TARGET.relative_to(ROOT)} with sizes {', '.join(map(str, SIZES))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
