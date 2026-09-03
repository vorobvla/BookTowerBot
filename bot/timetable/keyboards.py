"""Inline keyboard generators for timetable date and location selection."""

from typing import Callable, List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards import CB_TIMETABLE

# Callback prefixes
CB_TT_DATE_PREFIX = "tt_date:"
CB_TT_LOC_PREFIX = "tt_loc:"
CB_TT_DATES = "tt_dates"

CB_CA_DATE_PREFIX = "ca_date:"
CB_CA_LOC_PREFIX = "ca_loc:"
CB_CA_DATES = "ca_dates"


BTN_BACK_TO_DATES = "« Назад к выбору даты"
BTN_OTHER_LOCATION = "« Другая площадка"
BTN_CHOOSE_OTHER_DATE = "🗓 Выбрать другую дату"

# Callback map for timetable navigation buttons
TIMETABLE_CALLBACK_MAP = {
    BTN_BACK_TO_DATES: CB_TIMETABLE,
    BTN_CHOOSE_OTHER_DATE: CB_TIMETABLE,
}


def get_dates_inline_keyboard(
    dates: List[str],
    date_formatter: Optional[Callable[[str], str]] = None,
    date_prefix: str = CB_TT_DATE_PREFIX,
) -> InlineKeyboardMarkup:
    """Generate inline keyboard for available timetable dates."""
    keyboard: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    for date_str in dates:
        label = date_formatter(date_str) if date_formatter else date_str
        btn = InlineKeyboardButton(
            text=f"🗓 {label}",
            callback_data=f"{date_prefix}{date_str}",
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
    loc_prefix: str = CB_TT_LOC_PREFIX,
    back_cb: str = CB_TIMETABLE,
) -> InlineKeyboardMarkup:
    """Generate inline keyboard for available locations on a specific date."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for idx, loc in enumerate(locations):
        btn = InlineKeyboardButton(
            text=f"📍 {loc}",
            callback_data=f"{loc_prefix}{date_str}:{idx}",
        )
        keyboard.append([btn])

    # Back button to return to dates selection
    keyboard.append([
        InlineKeyboardButton(
            text=BTN_BACK_TO_DATES,
            callback_data=back_cb,
        )
    ])

    return InlineKeyboardMarkup(keyboard)


def get_timetable_details_keyboard(
    date_str: str,
    date_prefix: str = CB_TT_DATE_PREFIX,
    back_cb: str = CB_TIMETABLE,
) -> InlineKeyboardMarkup:
    """Generate navigation keyboard when viewing timetable events."""
    keyboard = [
        [
            InlineKeyboardButton(
                text=BTN_OTHER_LOCATION,
                callback_data=f"{date_prefix}{date_str}",
            )
        ],
        [
            InlineKeyboardButton(
                text=BTN_CHOOSE_OTHER_DATE,
                callback_data=back_cb,
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
