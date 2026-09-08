"""In-memory thread-safe chat registry for BookTowerBot broadcasts."""

import logging
import threading
from typing import List, Set

logger = logging.getLogger(__name__)


class ChatRegistry:
    """Thread-safe in-memory registry for Telegram chat IDs (strictly stored in RAM)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._chat_ids: Set[int] = set()

    def register(self, chat_id: int) -> bool:
        """Register a chat ID in memory. Returns True if newly added, False if already present."""
        if not chat_id or not isinstance(chat_id, int):
            try:
                chat_id = int(chat_id)
            except (ValueError, TypeError):
                return False

        with self._lock:
            if chat_id in self._chat_ids:
                return False
            self._chat_ids.add(chat_id)
            logger.debug("Registered chat_id %d in memory. Total: %d", chat_id, len(self._chat_ids))
            return True

    def unregister(self, chat_id: int) -> bool:
        """Remove a chat ID from memory. Returns True if removed, False if not found."""
        try:
            chat_id = int(chat_id)
        except (ValueError, TypeError):
            return False

        with self._lock:
            if chat_id in self._chat_ids:
                self._chat_ids.remove(chat_id)
                logger.debug("Unregistered chat_id %d from memory. Total: %d", chat_id, len(self._chat_ids))
                return True
            return False

    def is_registered(self, chat_id: int) -> bool:
        """Check if chat ID is currently stored in memory."""
        try:
            chat_id = int(chat_id)
        except (ValueError, TypeError):
            return False

        with self._lock:
            return chat_id in self._chat_ids

    def get_all(self) -> List[int]:
        """Return a copy of all registered chat IDs."""
        with self._lock:
            return list(self._chat_ids)

    def count(self) -> int:
        """Return the number of unique active chat IDs in memory."""
        with self._lock:
            return len(self._chat_ids)

    def clear(self) -> None:
        """Clear all registered chat IDs from memory."""
        with self._lock:
            self._chat_ids.clear()
            logger.debug("Cleared all chat IDs from memory registry.")


# Shared default chat registry instance
default_chat_registry = ChatRegistry()
