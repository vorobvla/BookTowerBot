"""Keyboard builders for Master Classes navigation."""

from typing import Callable, List, Optional, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.content import (
    BTN_BACK_TO_MC,
    BTN_MC_ALL,
    BTN_MC_FOR_CHILDREN,
    CB_MC_FILTER_ALL,
    CB_MC_FILTER_CHILDREN,
    CB_MC_ITEM_PREFIX,
)
from bot.timetable.event import Event

MASTER_CLASSES_CALLBACK_MAP = {
    BTN_MC_FOR_CHILDREN: CB_MC_FILTER_CHILDREN,
    BTN_MC_ALL: CB_MC_FILTER_ALL,
    BTN_BACK_TO_MC: CB_MC_FILTER_ALL,
}


def get_master_classes_inline_keyboard(
    master_classes: List[Tuple[str, int, Event]],
    children_only: bool = False,
    date_formatter: Optional[Callable[[str], str]] = None,
) -> InlineKeyboardMarkup:
    """Build inline keyboard for master classes list with filter button and event items."""
    keyboard: List[List[InlineKeyboardButton]] = []

    # Top filter toggle button
    if children_only:
        keyboard.append([
            InlineKeyboardButton(
                text=BTN_MC_ALL,
                callback_data=CB_MC_FILTER_ALL,
            )
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(
                text=BTN_MC_FOR_CHILDREN,
                callback_data=CB_MC_FILTER_CHILDREN,
            )
        ])

    # Event buttons (date and name)
    for date_str, idx, event in master_classes:
        if date_formatter:
            date_label = date_formatter(date_str)
        elif len(date_str) == 8 and date_str.isdigit():
            date_label = f"{date_str[:2]}.{date_str[2:4]}"
        else:
            date_label = date_str

        btn_text = f"{date_label} — {event.title}"
        callback_data = f"{CB_MC_ITEM_PREFIX}{date_str}:{idx}:{1 if children_only else 0}"
        keyboard.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=callback_data,
            )
        ])

    return InlineKeyboardMarkup(keyboard)


def get_master_class_details_keyboard(
    children_only: bool = False,
) -> InlineKeyboardMarkup:
    """Build inline keyboard for viewing a single master class details."""
    back_cb = CB_MC_FILTER_CHILDREN if children_only else CB_MC_FILTER_ALL
    keyboard = [
        [
            InlineKeyboardButton(
                text=BTN_BACK_TO_MC,
                callback_data=back_cb,
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
