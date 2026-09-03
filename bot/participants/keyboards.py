"""Inline keyboard generators for participants list and details selection."""

from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.content import (
    BTN_BACK_TO_MAP,
    BUTTON_CALLBACK_MAP,
    CB_PARTICIPANTS,
    CB_STAND_PREFIX,
)
from bot.participants.participant import Participant

CB_PART_ITEM_PREFIX = "part_item:"
CB_PARTICIPANTS_LIST = "participants_list"


BTN_BACK_TO_PARTICIPANTS = "« Назад к списку участников"

# Callback map for participant navigation buttons
PARTICIPANTS_CALLBACK_MAP = {
    BTN_BACK_TO_PARTICIPANTS: CB_PARTICIPANTS,
}


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


def get_stand_participants_inline_keyboard(
    participants: List[Participant],
    all_participants: Optional[List[Participant]] = None,
    stand_key: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Generate inline keyboard for participants on a specific stand with navigation back to map."""
    if all_participants is None:
        from bot.participants.service import ParticipantsService
        all_participants = ParticipantsService().get_participants()

    if stand_key is None and participants:
        from bot.participants.service import ParticipantsService
        stands = ParticipantsService().get_stands()
        stand_val = participants[0].stand.strip()
        try:
            stand_key = str(stands.index(stand_val))
        except ValueError:
            stand_key = stand_val

    keyboard: List[List[InlineKeyboardButton]] = []
    for p in participants:
        try:
            idx = all_participants.index(p)
        except ValueError:
            idx = next(
                (i for i, item in enumerate(all_participants) if item.name == p.name and item.stand == p.stand),
                0,
            )
        callback_data = (
            f"{CB_PART_ITEM_PREFIX}{idx}:s:{stand_key}"
            if stand_key is not None
            else f"{CB_PART_ITEM_PREFIX}{idx}"
        )
        btn = InlineKeyboardButton(
            text=p.format_button_label(),
            callback_data=callback_data,
        )
        keyboard.append([btn])

    keyboard.append([
        InlineKeyboardButton(
            text=BTN_BACK_TO_MAP,
            callback_data=BUTTON_CALLBACK_MAP[BTN_BACK_TO_MAP],
        )
    ])
    return InlineKeyboardMarkup(keyboard)


def get_participant_details_keyboard(
    stand_key: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Generate navigation keyboard when viewing individual participant details."""
    back_cb = (
        f"{CB_STAND_PREFIX}{stand_key}"
        if stand_key is not None
        else PARTICIPANTS_CALLBACK_MAP.get(BTN_BACK_TO_PARTICIPANTS, CB_PARTICIPANTS)
    )
    keyboard = [
        [
            InlineKeyboardButton(
                text=BTN_BACK_TO_PARTICIPANTS,
                callback_data=back_cb,
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
