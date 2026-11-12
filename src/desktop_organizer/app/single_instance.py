"""Only one running instance per data folder; a second start brings the first to the front."""

from __future__ import annotations

import hashlib

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance(QObject):
    activated = Signal()

    def __init__(self, key: str) -> None:
        super().__init__()
        # Local server names must be short and free of path characters.
        self._name = "DesktopOrganizer-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        self._server: QLocalServer | None = None

    def acquire(self) -> bool:
        """Return True if this is the first instance. Otherwise notify the running one."""
        socket = QLocalSocket()
        socket.connectToServer(self._name)
        if socket.waitForConnected(300):
            socket.write(b"activate")
            socket.waitForBytesWritten(300)
            socket.disconnectFromServer()
            return False

        QLocalServer.removeServer(self._name)  # stale name after a crash
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._on_connection)
        # If listening fails (rare), run anyway rather than refuse to start.
        self._server.listen(self._name)
        return True

    def _on_connection(self) -> None:
        if self._server is None:
            return
        connection = self._server.nextPendingConnection()
        if connection is not None:
            connection.disconnected.connect(connection.deleteLater)
            self.activated.emit()
