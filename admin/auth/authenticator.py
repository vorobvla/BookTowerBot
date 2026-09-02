"""Secure credential storage and authentication using SQLite and cryptographic hashing."""

import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from admin.config import AdminConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_relative_path(path: str) -> str:
    p = Path(path)
    if not p.is_absolute():
        return str((PROJECT_ROOT / p).resolve())
    return str(p.resolve())


class AdminAuthenticator:
    """Handles credentials storage, verification, registration, and confirmation."""

    def __init__(
        self,
        config: Optional[AdminConfig] = None,
        db_path: Optional[str] = None,
    ):
        self.config = config or AdminConfig.from_env()
        raw_db_path = db_path or getattr(self.config, "auth_db_path", str(PROJECT_ROOT / "assets" / "db" / "admin_users.db"))
        if raw_db_path == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = _resolve_relative_path(raw_db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a connection to the SQLite database."""
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize SQLite database schema for admin users."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    is_confirmed INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    @staticmethod
    def _hash_password(password: str, salt_hex: str) -> str:
        """Hash password using scrypt with given salt."""
        salt_bytes = bytes.fromhex(salt_hex)
        hash_bytes = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt_bytes,
            n=16384,
            r=8,
            p=1,
            maxmem=32 * 1024 * 1024,
        )
        return hash_bytes.hex()

    def register(self, username: Optional[str], password: Optional[str]) -> Tuple[bool, str]:
        """Register a new admin user in pending (unconfirmed) status."""
        if not username or not username.strip():
            return False, "Username cannot be empty"

        username_clean = username.strip()
        if len(username_clean) < 3:
            return False, "Username must be at least 3 characters long"

        if not re.match(r"^[A-Za-z0-9_.\-]+$", username_clean):
            return False, "Username can only contain letters, numbers, hyphens, dots, and underscores"

        if not password or len(password) < 6:
            return False, "Password must be at least 6 characters long"

        salt_hex = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt_hex)

        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO admin_users (username, password_hash, salt, is_confirmed)
                    VALUES (?, ?, ?, 0)
                    """,
                    (username_clean, password_hash, salt_hex),
                )
                conn.commit()
            return True, "Registration successful! Account is awaiting administrator approval."
        except sqlite3.IntegrityError:
            return False, "User with this username already exists"
        except Exception as e:
            return False, f"Registration error: {e}"

    def authenticate(self, username: Optional[str], password: Optional[str]) -> bool:
        """Verify username and password against database, requiring is_confirmed == 1."""
        if not username or not password:
            return False

        username_clean = username.strip()
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT password_hash, salt, is_confirmed
                FROM admin_users
                WHERE username = ?
                """,
                (username_clean,),
            ).fetchone()

        if not row:
            return False

        if row["is_confirmed"] != 1:
            return False

        expected_hash = row["password_hash"]
        salt_hex = row["salt"]
        computed_hash = self._hash_password(password, salt_hex)

        return hmac.compare_digest(computed_hash, expected_hash)

    def is_confirmed(self, username: Optional[str]) -> bool:
        """Check if user exists and is confirmed."""
        if not username:
            return False

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT is_confirmed FROM admin_users WHERE username = ?",
                (username.strip(),),
            ).fetchone()

        if not row:
            return False
        return row["is_confirmed"] == 1

    def user_exists(self, username: Optional[str]) -> bool:
        """Check if user with given username already exists."""
        if not username:
            return False

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM admin_users WHERE username = ?",
                (username.strip(),),
            ).fetchone()
        return bool(row)

    def approve_user(self, username: str) -> bool:
        """Approve (confirm) an admin user."""
        if not username:
            return False

        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE admin_users SET is_confirmed = 1 WHERE username = ?",
                (username.strip(),),
            )
            conn.commit()
            return cursor.rowcount > 0

    def reject_user(self, username: str) -> bool:
        """Reject and remove a user registration."""
        if not username:
            return False

        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM admin_users WHERE username = ?",
                (username.strip(),),
            )
            conn.commit()
            return cursor.rowcount > 0

    def clear_pending_users(self) -> int:
        """Clear all non-approved (pending) user registrations."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM admin_users WHERE is_confirmed = 0")
            conn.commit()
            return cursor.rowcount

    def list_pending_users(self) -> List[Dict[str, Any]]:
        """List all users waiting for confirmation."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, username, created_at
                FROM admin_users
                WHERE is_confirmed = 0
                ORDER BY created_at ASC
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def list_all_users(self) -> List[Dict[str, Any]]:
        """List all registered users and their confirmation status."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, username, is_confirmed, created_at
                FROM admin_users
                ORDER BY created_at ASC
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def create_admin_user(self, username: str, password: str, is_confirmed: bool = True) -> bool:
        """Directly create or replace a confirmed admin user."""
        if not username or not password:
            return False

        salt_hex = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt_hex)
        confirmed_val = 1 if is_confirmed else 0

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO admin_users (username, password_hash, salt, is_confirmed)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password_hash = excluded.password_hash,
                    salt = excluded.salt,
                    is_confirmed = excluded.is_confirmed
                """,
                (username.strip(), password_hash, salt_hex, confirmed_val),
            )
            conn.commit()
        return True
