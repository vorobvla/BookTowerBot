"""Keyboards for Telegram bot interactions."""

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
    BTN_TIMETABLE,
    BUTTON_CALLBACK_MAP,
    CB_CHILDREN_ACTIVITY,
    CB_HELP,
    CB_MAP,
    CB_PARTICIPANTS,
    CB_RECOMMENDATIONS,
    CB_TIMETABLE,
)


def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Returns the persistent main menu reply keyboard."""
    keyboard = [
        [KeyboardButton(BTN_MAP), KeyboardButton(BTN_TIMETABLE)],
        [KeyboardButton(BTN_CHILDREN_ACTIVITY), KeyboardButton(BTN_RECOMMENDATIONS)],
        [KeyboardButton(BTN_PARTICIPANTS), KeyboardButton(BTN_HELP)],
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
            InlineKeyboardButton(BTN_HELP, callback_data=BUTTON_CALLBACK_MAP[BTN_HELP]),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_map_inline_keyboard() -> InlineKeyboardMarkup:
    """Returns an inline keyboard with a single 'Show participants' button."""
    keyboard = [
        [
            InlineKeyboardButton(BTN_SHOW_PARTICIPANTS, callback_data=BUTTON_CALLBACK_MAP[BTN_SHOW_PARTICIPANTS]),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
