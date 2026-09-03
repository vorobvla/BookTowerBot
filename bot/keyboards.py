"""Keyboards for Telegram bot interactions."""

from typing import List, Optional
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.content import (
    BTN_CHILDREN_ACTIVITY,
    BTN_HELP,
    BTN_MAP,
    BTN_PARTICIPANTS,
    BTN_RECOMMENDATIONS,
    BTN_SHOW_PARTICIPANTS,
    BTN_SHOW_STANDS,
    BTN_TIMETABLE,
    BTN_WISHLIST,
    BUTTON_CALLBACK_MAP,
    CB_CHILDREN_ACTIVITY,
    CB_HELP,
    CB_MAP,
    CB_PARTICIPANTS,
    CB_RECOMMENDATIONS,
    CB_STANDS,
    CB_STAND_PREFIX,
    CB_TIMETABLE,
    CB_WISHLIST,
)
from bot.wishlist.keyboards import get_wishlist_inline_keyboard


def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Returns the persistent main menu reply keyboard."""
    keyboard = [
        [KeyboardButton(BTN_MAP), KeyboardButton(BTN_TIMETABLE)],
        [KeyboardButton(BTN_CHILDREN_ACTIVITY), KeyboardButton(BTN_RECOMMENDATIONS)],
        [KeyboardButton(BTN_PARTICIPANTS), KeyboardButton(BTN_WISHLIST)],
        [KeyboardButton(BTN_HELP)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_main_inline_keyboard() -> InlineKeyboardMarkup:
    """Returns an inline keyboard with the primary navigation actions."""
    keyboard = [
        [
            InlineKeyboardButton(BTN_MAP, callback_data=BUTTON_CALLBACK_MAP[BTN_MAP]),
            InlineKeyboardButton(BTN_TIMETABLE, callback_data=BUTTON_CALLBACK_MAP[BTN_TIMETABLE]),
        ],
        [
            InlineKeyboardButton(BTN_CHILDREN_ACTIVITY, callback_data=BUTTON_CALLBACK_MAP[BTN_CHILDREN_ACTIVITY]),
            InlineKeyboardButton(BTN_RECOMMENDATIONS, callback_data=BUTTON_CALLBACK_MAP[BTN_RECOMMENDATIONS]),
        ],
        [
            InlineKeyboardButton(BTN_PARTICIPANTS, callback_data=BUTTON_CALLBACK_MAP[BTN_PARTICIPANTS]),
            InlineKeyboardButton(BTN_WISHLIST, callback_data=BUTTON_CALLBACK_MAP[BTN_WISHLIST]),
        ],
        [
            InlineKeyboardButton(BTN_HELP, callback_data=BUTTON_CALLBACK_MAP[BTN_HELP]),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_map_inline_keyboard() -> InlineKeyboardMarkup:
    """Returns an inline keyboard with a single 'Show stands info' button."""
    keyboard = [
        [
            InlineKeyboardButton(
                BTN_SHOW_STANDS,
                callback_data=BUTTON_CALLBACK_MAP.get(BTN_SHOW_STANDS, CB_STANDS),
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_stands_grid_inline_keyboard(
    stands: Optional[List[str]] = None,
    columns: int = 4,
) -> InlineKeyboardMarkup:
    """Returns an inline keyboard arranged in a grid with only the names of stands."""
    if stands is None:
        from bot.participants.service import ParticipantsService

        stands = ParticipantsService().get_stands()

    keyboard: List[List[InlineKeyboardButton]] = []
    if not stands:
        return InlineKeyboardMarkup(keyboard)

    for i in range(0, len(stands), columns):
        row = []
        for idx, stand in enumerate(stands[i : i + columns], start=i):
            btn = InlineKeyboardButton(
                text=str(stand),
                callback_data=f"{CB_STAND_PREFIX}{idx}",
            )
            row.append(btn)
        keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)
