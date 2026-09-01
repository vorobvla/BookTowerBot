"""HTTP Server wrapper for running the admin console."""

import threading
from http.server import HTTPServer, ThreadingHTTPServer
from typing import Optional

from admin.config import AdminConfig
from admin.server.handler import AdminHttpHandler
from admin.server.router import AdminRouter


class AdminServer:
    """Manages the lifecycle of the Admin HTTP server."""

    def __init__(self, router: AdminRouter, config: Optional[AdminConfig] = None):
        self.config = config or AdminConfig.from_env()
        self.router = router
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, background: bool = False) -> None:
        """Start the HTTP server on configured host and port."""
        handler_cls = type("BoundAdminHttpHandler", (AdminHttpHandler,), {"router": self.router})
        self._server = ThreadingHTTPServer((self.config.host, self.config.port), handler_cls)

        if background:
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
        else:
            try:
                self._server.serve_forever()
            except KeyboardInterrupt:
                self.stop()

    def stop(self) -> None:
        """Stop and shutdown the HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None

    @property
    def is_running(self) -> bool:
        """Check if server is currently running."""
        return self._server is not None
