"""Inline keyboard generators for participants list and details selection."""

from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.content import CB_PARTICIPANTS
from bot.participants.participant import Participant

CB_PART_ITEM_PREFIX = "part_item:"
CB_PARTICIPANTS_LIST = "participants_list"


def get_participants_inline_keyboard(participants: List[Participant]) -> InlineKeyboardMarkup:
    """Generate inline keyboard for available participants sorted by stand."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for idx, p in enumerate(participants):
        btn = InlineKeyboardButton(
            text=p.format_button_label(),
            callback_data=f"{CB_PART_ITEM_PREFIX}{idx}",
        )
        keyboard.append([btn])

    return InlineKeyboardMarkup(keyboard)


def get_participant_details_keyboard() -> InlineKeyboardMarkup:
    """Generate navigation keyboard when viewing individual participant details."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="« Назад к списку участников",
                callback_data=CB_PARTICIPANTS,
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
