"""Session management for authenticated admin users."""

import secrets
import time
from typing import Dict, Optional


class AdminSessionManager:
    """Manages creation, validation, and destruction of admin sessions."""

    def __init__(self, timeout_seconds: int = 3600 * 24):
        self.timeout_seconds = timeout_seconds
        self._sessions: Dict[str, float] = {}  # token -> expiration timestamp

    def create_session(self) -> str:
        """Create a new session token and register it with expiration."""
        self._cleanup_expired()
        token = secrets.token_hex(32)
        self._sessions[token] = time.time() + self.timeout_seconds
        return token

    def is_valid_session(self, token: Optional[str]) -> bool:
        """Check whether a session token is active and valid."""
        if not token or token not in self._sessions:
            return False

        if time.time() > self._sessions[token]:
            del self._sessions[token]
            return False

        return True

    def revoke_session(self, token: Optional[str]) -> None:
        """Invalidate and delete a session token."""
        if token and token in self._sessions:
            del self._sessions[token]

    def _cleanup_expired(self) -> None:
        """Remove expired tokens to maintain memory hygiene."""
        now = time.time()
        expired = [token for token, expires in self._sessions.items() if now > expires]
        for token in expired:
            del self._sessions[token]
