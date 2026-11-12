"""One running instance per key; a second start forwards its request to the first.

The main window and every tool window use their own key, so starting a tool that is
already open brings its window to the front instead of opening a second copy.
"""

from __future__ import annotations

import hashlib

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance(QObject):
    message_received = Signal(str)

    def __init__(self, key: str) -> None:
        super().__init__()
        # Local server names must be short and free of path characters.
        self._name = "DesktopOrganizer-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
        self._server: QLocalServer | None = None

    @property
    def name(self) -> str:
        return self._name

    def acquire(self, message: str = "activate") -> bool:
        """Return True if this is the first instance; otherwise send ``message`` to it."""
        socket = QLocalSocket()
        socket.connectToServer(self._name)
        if socket.waitForConnected(500):
            socket.write(message.encode("utf-8"))
            socket.flush()
            socket.waitForBytesWritten(500)
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
        if connection is None:
            return

        def read() -> None:
            data = bytes(connection.readAll().data()).decode("utf-8", errors="replace")
            for line in filter(None, data.splitlines()):
                self.message_received.emit(line)

        connection.readyRead.connect(read)
        connection.disconnected.connect(connection.deleteLater)
        if connection.bytesAvailable():
            read()
