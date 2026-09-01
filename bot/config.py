import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Bot configuration settings."""
    bot_token: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        return cls(bot_token=token)
