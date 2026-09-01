"""User authentication for the admin console."""

import hmac
from typing import Optional

from admin.config import AdminConfig


class AdminAuthenticator:
    """Handles credentials verification and authentication."""

    def __init__(self, config: Optional[AdminConfig] = None):
        self.config = config or AdminConfig.from_env()

    def authenticate(self, username: Optional[str], password: Optional[str]) -> bool:
        """Verify username and password against configured admin credentials."""
        if not username or not password:
            return False

        user_match = hmac.compare_digest(username.strip(), self.config.username.strip())
        pass_match = hmac.compare_digest(password.strip(), self.config.password.strip())

        return user_match and pass_match
