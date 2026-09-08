import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Config:
    """Bot configuration settings."""
    bot_token: str
    internal_host: str = "127.0.0.1"
    internal_port: int = 8085

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        host = os.getenv("BOT_INTERNAL_HOST", "127.0.0.1").strip()
        port_str = os.getenv("BOT_INTERNAL_PORT", "8085").strip()
        try:
            port = int(port_str)
        except ValueError:
            port = 8085
        return cls(bot_token=token, internal_host=host, internal_port=port)
