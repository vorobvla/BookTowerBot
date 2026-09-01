"""Recommendations package for book compilations and picks."""

from bot.recommendations.book import Book
from bot.recommendations.category import RecommendationCategory
from bot.recommendations.keyboards import (
    CB_REC_CATEGORY_PREFIX,
    CB_RECS_CATEGORIES,
    get_categories_inline_keyboard,
    get_recommendation_details_keyboard,
)
from bot.recommendations.service import RecommendationsService

__all__ = [
    "Book",
    "RecommendationCategory",
    "RecommendationsService",
    "CB_REC_CATEGORY_PREFIX",
    "CB_RECS_CATEGORIES",
    "get_categories_inline_keyboard",
    "get_recommendation_details_keyboard",
]
