"""Configuration settings for the Admin console."""

import os
from dataclasses import dataclass
from typing import Optional

from bot.content import ASSETS_PATH, RECS_PATH, TIMETABLES_PATH


@dataclass(frozen=True)
class AdminConfig:
    """Admin application configuration settings."""

    host: str = "0.0.0.0"
    port: int = 8080
    username: str = "admin"
    password: str = "admin"
    session_cookie_name: str = "booktower_admin_session"
    session_timeout_seconds: int = 3600 * 24  # 24 hours
    assets_path: str = ASSETS_PATH
    recs_path: str = RECS_PATH
    timetables_path: str = TIMETABLES_PATH

    @classmethod
    def from_env(cls) -> "AdminConfig":
        """Load configuration from environment variables with sensible defaults."""
        host = os.getenv("ADMIN_HOST", "0.0.0.0").strip()
        port_str = os.getenv("ADMIN_PORT", "8080").strip()
        try:
            port = int(port_str)
        except ValueError:
            port = 8080

        username = os.getenv("ADMIN_USERNAME", "admin").strip()
        password = os.getenv("ADMIN_PASSWORD", "admin").strip()

        assets_path = os.getenv("ASSETS_PATH", ASSETS_PATH).strip()
        recs_path = os.getenv("RECS_PATH", os.path.join(assets_path, "recs", "recs.json")).strip()
        timetables_path = os.getenv("TIMETABLES_PATH", os.path.join(assets_path, "timetables")).strip()

        return cls(
            host=host,
            port=port,
            username=username,
            password=password,
            assets_path=assets_path,
            recs_path=recs_path,
            timetables_path=timetables_path,
        )
