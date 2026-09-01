"""Inline keyboard generators for recommendation category and book selection."""

from typing import Any, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards import CB_RECOMMENDATIONS

# Callback prefixes
CB_REC_CATEGORY_PREFIX = "rec_cat:"
CB_RECS_CATEGORIES = "recs_categories"


def get_categories_inline_keyboard(categories: List[Any]) -> InlineKeyboardMarkup:
    """Generate inline keyboard for available recommendation categories."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for cat in categories:
        if hasattr(cat, "name"):
            cat_name = cat.name
            emoji = getattr(cat, "emoji", "") or "📚"
            btn_text = f"{emoji} {cat_name}" if not cat_name.startswith(emoji) else cat_name
        else:
            cat_name = str(cat)
            btn_text = f"📚 {cat_name}"

        btn = InlineKeyboardButton(
            text=btn_text,
            callback_data=f"{CB_REC_CATEGORY_PREFIX}{cat_name}",
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
