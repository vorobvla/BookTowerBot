"""Admin Broadcast service communicating with the Bot process via internal loopback API."""

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from bot.broadcast.service import AVAILABLE_BROADCAST_COMMANDS

logger = logging.getLogger(__name__)


class AdminBroadcastService:
    """Service client for Admin Console to query bot status and dispatch broadcasts."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 8085,
        timeout: float = 15.0,
    ) -> None:
        if api_url:
            self.api_url = api_url.rstrip("/")
        else:
            self.api_url = f"http://{host}:{port}"
        self.timeout = timeout

    def _get(self, endpoint: str) -> Dict[str, Any]:
        """Send HTTP GET request to internal loopback API."""
        url = f"{self.api_url}{endpoint}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8")
                return json.loads(err_body)
            except Exception:
                return {"status": "error", "message": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            logger.debug("Failed GET %s: %s", url, e)
            return {"status": "offline", "message": f"Bot process unreachable: {e}"}

    def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send HTTP POST request with JSON payload to internal loopback API."""
        url = f"{self.api_url}{endpoint}"
        json_data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=json_data,
            headers={"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8")
                return json.loads(err_body)
            except Exception:
                return {"status": "error", "message": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            logger.error("Failed POST %s: %s", url, e, exc_info=True)
            return {"status": "offline", "message": f"Bot process unreachable: {e}"}

    def get_status(self) -> Dict[str, Any]:
        """Query active status and registered chat count from the Bot process."""
        result = self._get("/internal/chats/count")
        if result.get("status") == "ok":
            return {
                "online": True,
                "status": "ok",
                "chat_count": result.get("chat_count", 0),
                "total_chats": result.get("total_chats", 0),
            }
        return {
            "online": False,
            "status": "offline",
            "chat_count": 0,
            "total_chats": 0,
            "error": result.get("message", "Bot process is currently unreachable"),
        }

    def get_chat_count(self) -> int:
        """Get the count of active registered Telegram chats."""
        status = self.get_status()
        return status.get("chat_count", 0)

    def get_available_commands(self) -> List[Dict[str, str]]:
        """Retrieve list of commands available for broadcasting."""
        res = self._get("/internal/commands")
        if res.get("status") == "ok" and isinstance(res.get("commands"), list):
            return res["commands"]
        return AVAILABLE_BROADCAST_COMMANDS

    def broadcast_message(self, text: str, parse_mode: str = "Markdown") -> Dict[str, Any]:
        """Dispatch custom text message broadcast."""
        return self._post("/internal/broadcast/message", {
            "text": text,
            "parse_mode": parse_mode,
        })

    def broadcast_command(self, command: str) -> Dict[str, Any]:
        """Dispatch command broadcast."""
        return self._post("/internal/broadcast/command", {
            "command": command,
        })

    def broadcast(
        self,
        text: Optional[str] = None,
        command: Optional[str] = None,
        parse_mode: str = "Markdown",
    ) -> Dict[str, Any]:
        """Dispatch composite broadcast (text, command, or both)."""
        payload: Dict[str, Any] = {"parse_mode": parse_mode}
        if text and text.strip():
            payload["text"] = text.strip()
        if command and command.strip():
            payload["command"] = command.strip()
        return self._post("/internal/broadcast", payload)
