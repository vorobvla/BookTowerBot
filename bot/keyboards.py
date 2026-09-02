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
    BTN_RECOMMENDATIONS,
    BTN_TIMETABLE,
    CB_CHILDREN_ACTIVITY,
)

# Callback data constants
CB_MAP = "action_map"
CB_TIMETABLE = "action_timetable"
CB_RECOMMENDATIONS = "action_recommendations"
CB_HELP = "action_help"


def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Returns the persistent main menu reply keyboard."""
    keyboard = [
        [KeyboardButton(BTN_MAP), KeyboardButton(BTN_TIMETABLE)],
        [KeyboardButton(BTN_CHILDREN_ACTIVITY), KeyboardButton(BTN_RECOMMENDATIONS)],
        [KeyboardButton(BTN_HELP)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_main_inline_keyboard() -> InlineKeyboardMarkup:
    """Returns an inline keyboard with the primary navigation actions."""
    keyboard = [
        [
            InlineKeyboardButton(BTN_MAP, callback_data=CB_MAP),
            InlineKeyboardButton(BTN_TIMETABLE, callback_data=CB_TIMETABLE),
        ],
        [
            InlineKeyboardButton(BTN_CHILDREN_ACTIVITY, callback_data=CB_CHILDREN_ACTIVITY),
            InlineKeyboardButton(BTN_RECOMMENDATIONS, callback_data=CB_RECOMMENDATIONS),
        ],
        [
            InlineKeyboardButton(BTN_HELP, callback_data=CB_HELP),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
