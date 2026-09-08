"""Internal loopback HTTP server for Bot process enabling Admin-Bot communication."""

import asyncio
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from bot.broadcast.service import BroadcastService

logger = logging.getLogger(__name__)


class BotInternalHttpHandler(BaseHTTPRequestHandler):
    """Request handler for bot internal loopback API endpoints."""

    server: "BotInternalServer"

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress standard stderr log messages or log to debug."""
        logger.debug("BotInternalServer: " + format, *args)

    def _send_json(self, status_code: int, data: Dict[str, Any]) -> None:
        """Send JSON HTTP response with headers."""
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.error("Error writing JSON response: %s", e)

    def _execute_async(self, coro: Any) -> Any:
        """Execute async coroutine on the bot event loop or a new event loop."""
        loop = getattr(self.server, "loop", None)
        if loop is not None and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=60.0)
        else:
            return asyncio.run(coro)

    def do_OPTIONS(self) -> None:
        """Handle CORS pre-flight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:
        """Handle GET requests for chat count, commands catalog, and health check."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if not path:
            path = "/"

        broadcast_service: BroadcastService = self.server.broadcast_service

        if path in ("/internal/chats/count", "/internal/chats", "/internal/status", "/internal/count"):
            count = broadcast_service.registry.count()
            self._send_json(200, {
                "status": "ok",
                "chat_count": count,
                "total_chats": count,
            })
            return

        if path in ("/internal/commands", "/internal/broadcast/commands"):
            commands = broadcast_service.get_available_commands()
            self._send_json(200, {
                "status": "ok",
                "commands": commands,
            })
            return

        if path in ("/internal/health", "/health", "/ping"):
            self._send_json(200, {"status": "ok", "service": "booktower_bot_internal"})
            return

        self._send_json(404, {"status": "error", "message": f"Endpoint not found: {self.path}"})

    def do_POST(self) -> None:
        """Handle POST requests for broadcasts (composite, message, command)."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if not path:
            path = "/"

        # Read request body
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception as e:
            self._send_json(400, {"status": "error", "message": f"Invalid JSON payload: {e}"})
            return

        broadcast_service: BroadcastService = self.server.broadcast_service

        if path in ("/internal/broadcast", "/internal/broadcast/send"):
            text = payload.get("text")
            command = payload.get("command")
            parse_mode = payload.get("parse_mode", "Markdown")
            try:
                result = self._execute_async(broadcast_service.broadcast(
                    text=text,
                    command=command,
                    parse_mode=parse_mode,
                ))
                status_code = 200 if result.get("status") == "ok" else 400
                self._send_json(status_code, result)
            except Exception as e:
                logger.error("Error executing broadcast: %s", e, exc_info=True)
                self._send_json(500, {"status": "error", "message": str(e)})
            return

        if path in ("/internal/broadcast/message", "/internal/broadcast/msg"):
            text = payload.get("text", "")
            parse_mode = payload.get("parse_mode", "Markdown")
            try:
                result = self._execute_async(broadcast_service.broadcast_message(
                    text=text,
                    parse_mode=parse_mode,
                ))
                status_code = 200 if result.get("status") == "ok" else 400
                self._send_json(status_code, result)
            except Exception as e:
                logger.error("Error executing message broadcast: %s", e, exc_info=True)
                self._send_json(500, {"status": "error", "message": str(e)})
            return

        if path in ("/internal/broadcast/command", "/internal/broadcast/cmd"):
            command = payload.get("command", "")
            try:
                result = self._execute_async(broadcast_service.broadcast_command(
                    command=command,
                ))
                status_code = 200 if result.get("status") == "ok" else 400
                self._send_json(status_code, result)
            except Exception as e:
                logger.error("Error executing command broadcast: %s", e, exc_info=True)
                self._send_json(500, {"status": "error", "message": str(e)})
            return

        self._send_json(404, {"status": "error", "message": f"Endpoint not found: {self.path}"})


class BotInternalServer(ThreadingHTTPServer):
    """Lightweight internal HTTP server running in the Bot process for Admin loopback calls."""

    allow_reuse_address = True

    def __init__(
        self,
        broadcast_service: BroadcastService,
        host: str = "127.0.0.1",
        port: int = 8085,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.broadcast_service = broadcast_service
        self.loop = loop
        self._thread: Optional[threading.Thread] = None

        super().__init__((host, port), BotInternalHttpHandler)

    def start(self, background: bool = True) -> None:
        """Start the internal server (by default in a background thread)."""
        logger.info("Starting BotInternalServer on http://%s:%d", self.host, self.port)
        if background:
            self._thread = threading.Thread(target=self.serve_forever, daemon=True)
            self._thread.start()
        else:
            try:
                self.serve_forever()
            except KeyboardInterrupt:
                self.stop()

    def stop(self) -> None:
        """Stop the internal server and cleanup threads."""
        logger.info("Stopping BotInternalServer...")
        try:
            self.shutdown()
            self.server_close()
        except Exception as e:
            logger.debug("Error during internal server shutdown: %s", e)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None

    @property
    def is_running(self) -> bool:
        """Check if server is active."""
        return self._thread is not None and self._thread.is_alive()
