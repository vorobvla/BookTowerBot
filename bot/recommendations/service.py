"""Service for loading and querying recommendations from JSON asset files."""

import json
import os
from typing import List, Optional

from bot.content import RECS_PATH
from bot.recommendations.category import RecommendationCategory


class RecommendationsService:
    """Service managing recommendation data loading, retrieval, and formatting."""

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or RECS_PATH

    def get_categories(self) -> List[RecommendationCategory]:
        """Load and return all recommendation categories from the JSON asset file."""
        if not os.path.exists(self.file_path):
            return []

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_recs = data.get("recs") or []
            categories = []
            for item in raw_recs:
                if isinstance(item, dict):
                    categories.append(RecommendationCategory.from_dict(item))
            return categories
        except Exception:
            return []

    def get_category_names(self) -> List[str]:
        """Return list of names for all available recommendation categories."""
        return [cat.name for cat in self.get_categories() if cat.name]

    def get_category(self, category_name: str) -> Optional[RecommendationCategory]:
        """Return RecommendationCategory matching the specified name."""
        target = category_name.strip().lower()
        for cat in self.get_categories():
            if cat.name.strip().lower() == target:
                return cat
        return None

    def format_category_recommendations(self, category_name: str) -> str:
        """Format recommendations for the specified category as Markdown."""
        cat = self.get_category(category_name)
        if not cat:
            return f"📚 *Рекомендации*\n\nПодборка «{category_name}» не найдена."
        return cat.format_markdown()
