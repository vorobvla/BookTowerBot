"""Inline keyboard generators for timetable date and location selection."""

from typing import Callable, List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards import CB_TIMETABLE

# Callback prefixes
CB_TT_DATE_PREFIX = "tt_date:"
CB_TT_LOC_PREFIX = "tt_loc:"
CB_TT_DATES = "tt_dates"


def get_dates_inline_keyboard(
    dates: List[str],
    date_formatter: Optional[Callable[[str], str]] = None,
) -> InlineKeyboardMarkup:
    """Generate inline keyboard for available timetable dates."""
    keyboard: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    for date_str in dates:
        label = date_formatter(date_str) if date_formatter else date_str
        btn = InlineKeyboardButton(
            text=f"🗓 {label}",
            callback_data=f"{CB_TT_DATE_PREFIX}{date_str}",
        )
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)


def get_locations_inline_keyboard(
    date_str: str,
    locations: List[str],
) -> InlineKeyboardMarkup:
    """Generate inline keyboard for available locations on a specific date."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for loc in locations:
        btn = InlineKeyboardButton(
            text=f"📍 {loc}",
            callback_data=f"{CB_TT_LOC_PREFIX}{date_str}:{loc}",
        )
        keyboard.append([btn])

    # Back button to return to dates selection
    keyboard.append([
        InlineKeyboardButton(
            text="« Назад к выбору даты",
            callback_data=CB_TIMETABLE,
        )
    ])

    return InlineKeyboardMarkup(keyboard)


def get_timetable_details_keyboard(date_str: str) -> InlineKeyboardMarkup:
    """Generate navigation keyboard when viewing timetable events."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="« Другая площадка",
                callback_data=f"{CB_TT_DATE_PREFIX}{date_str}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🗓 Выбрать другую дату",
                callback_data=CB_TIMETABLE,
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
