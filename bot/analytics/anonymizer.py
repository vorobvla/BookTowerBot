"""User ID anonymizer ensuring raw identifiers are never stored or exposed."""

import hashlib
import os
from typing import Optional, Union


def anonymize_user_id(
    telegram_id: Union[int, str],
    salt: Optional[str] = None,
) -> str:
    """Generate anonymized user_id by hashing telegram_id with secret salt.

    Raw telegram_ids are never stored in databases or shown in outputs.
    """
    effective_salt = salt or os.getenv("ANALYTICS_SALT") or os.getenv("WISHLIST_SALT") or "booktower_analytics_salt"
    raw = f"{effective_salt}:{telegram_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
