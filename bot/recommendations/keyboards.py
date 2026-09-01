"""Inline keyboard generators for recommendation category and book selection."""

from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards import CB_RECOMMENDATIONS

# Callback prefixes
CB_REC_CATEGORY_PREFIX = "rec_cat:"
CB_RECS_CATEGORIES = "recs_categories"


def get_categories_inline_keyboard(categories: List[str]) -> InlineKeyboardMarkup:
    """Generate inline keyboard for available recommendation categories."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for cat in categories:
        btn = InlineKeyboardButton(
            text=f"{cat}",
            callback_data=f"{CB_REC_CATEGORY_PREFIX}{cat}",
        )
        keyboard.append([btn])

    return InlineKeyboardMarkup(keyboard)


def get_recommendation_details_keyboard() -> InlineKeyboardMarkup:
    """Generate navigation keyboard when viewing book recommendations."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="« Другие категории",
                callback_data=CB_RECOMMENDATIONS,
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
