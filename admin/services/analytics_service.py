"""Admin analytics service providing aggregated metrics, user paths, and export."""

from typing import Any, Dict, List, Optional
from bot.analytics.service import AnalyticsService


class AdminAnalyticsService(AnalyticsService):
    """Admin-specific UX analytics and reporting service."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        wishlist_db_path: Optional[str] = None,
    ):
        super().__init__(db_path=db_path, wishlist_db_path=wishlist_db_path)
