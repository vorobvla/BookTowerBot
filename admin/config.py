"""Configuration settings for the Admin console."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from bot.content import ASSETS_PATH, MAP_DIR, MAP_PATH, PARTICIPANTS_PATH, RECS_PATH, TIMETABLES_PATH

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def _resolve_relative_path(path: str) -> str:
    p = Path(path)
    if not p.is_absolute():
        return str((PROJECT_ROOT / p).resolve())
    return str(p.resolve())


@dataclass(frozen=True)
class AdminConfig:
    """Admin application configuration settings."""

    host: str = "0.0.0.0"
    port: int = 8080
    auth_db_path: str = str(PROJECT_ROOT / "assets" / "db" / "admin_users.db")
    session_cookie_name: str = "booktower_admin_session"
    session_timeout_seconds: int = 3600 * 24  # 24 hours
    assets_path: str = ASSETS_PATH
    recs_path: str = RECS_PATH
    timetables_path: str = TIMETABLES_PATH
    participants_path: str = PARTICIPANTS_PATH
    map_dir: str = MAP_DIR
    map_path: str = MAP_PATH

    @classmethod
    def from_env(cls) -> "AdminConfig":
        """Load configuration from environment variables with sensible defaults."""
        host = os.getenv("ADMIN_HOST", "0.0.0.0").strip()
        port_str = os.getenv("ADMIN_PORT", "8080").strip()
        try:
            port = int(port_str)
        except ValueError:
            port = 8080

        auth_db_path_raw = (
            os.getenv("ADMIN_AUTH_DB_PATH")
            or os.getenv("ADMIN_DB_PATH")
            or os.getenv("AUTH_DB_PATH")
            or "assets/db/admin_users.db"
        ).strip()
        if auth_db_path_raw == ":memory:":
            auth_db_path = ":memory:"
        else:
            auth_db_path = _resolve_relative_path(auth_db_path_raw)

        session_cookie_name = (
            os.getenv("ADMIN_SESSION_COOKIE_NAME")
            or os.getenv("SESSION_COOKIE_NAME")
            or "booktower_admin_session"
        ).strip()

        session_timeout_str = (
            os.getenv("ADMIN_SESSION_TIMEOUT_SECONDS")
            or os.getenv("SESSION_TIMEOUT_SECONDS")
            or str(3600 * 24)
        ).strip()
        try:
            session_timeout_seconds = int(session_timeout_str)
        except ValueError:
            session_timeout_seconds = 3600 * 24

        assets_path = _resolve_relative_path(os.getenv("ASSETS_PATH", ASSETS_PATH).strip())
        recs_path = _resolve_relative_path(os.getenv("RECS_PATH", os.path.join(assets_path, "recs", "recs.json")).strip())
        timetables_path = _resolve_relative_path(os.getenv("TIMETABLES_PATH", os.path.join(assets_path, "timetables")).strip())
        participants_path = _resolve_relative_path(os.getenv("PARTICIPANTS_PATH", os.path.join(assets_path, "participants", "participants.json")).strip())
        map_dir = _resolve_relative_path(os.getenv("MAP_DIR", os.path.join(assets_path, "map")).strip())
        map_path = _resolve_relative_path(os.getenv("MAP_PATH", os.path.join(map_dir, "map.png")).strip())

        return cls(
            host=host,
            port=port,
            auth_db_path=auth_db_path,
            session_cookie_name=session_cookie_name,
            session_timeout_seconds=session_timeout_seconds,
            assets_path=assets_path,
            recs_path=recs_path,
            timetables_path=timetables_path,
            participants_path=participants_path,
            map_dir=map_dir,
            map_path=map_path,
        )
