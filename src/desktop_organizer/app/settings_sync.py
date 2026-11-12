"""Keep settings in sync between the main window and the tool processes."""

from __future__ import annotations

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer

from desktop_organizer.core.settings import Settings


class SettingsSync(QObject):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self._watcher = QFileSystemWatcher(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._reload)
        folder = str(settings.path.parent)
        self._watcher.addPath(folder)
        if settings.path.exists():
            self._watcher.addPath(str(settings.path))
        self._watcher.fileChanged.connect(lambda _p: self._timer.start())
        self._watcher.directoryChanged.connect(lambda _p: self._timer.start())

    def _reload(self) -> None:
        # Atomic replace drops the file watch on some systems; re-add it every time.
        path = str(self._settings.path)
        if self._settings.path.exists() and path not in self._watcher.files():
            self._watcher.addPath(path)
        self._settings.reload()
