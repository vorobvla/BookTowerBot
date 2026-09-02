"""Tests for keyboard layout builders."""

from bot.content import (
    BTN_CHILDREN_ACTIVITY,
    BTN_HELP,
    BTN_MAP,
    BTN_PARTICIPANTS,
    BTN_RECOMMENDATIONS,
    BTN_TIMETABLE,
    CB_CHILDREN_ACTIVITY,
    CB_PARTICIPANTS,
)
from bot.keyboards import (
    CB_HELP,
    CB_MAP,
    CB_RECOMMENDATIONS,
    CB_TIMETABLE,
    get_main_inline_keyboard,
    get_main_reply_keyboard,
)


def test_get_main_reply_keyboard():
    keyboard = get_main_reply_keyboard()
    assert keyboard.resize_keyboard is True

    buttons = [[btn.text for btn in row] for row in keyboard.keyboard]
    assert buttons == [
        [BTN_MAP, BTN_TIMETABLE],
        [BTN_CHILDREN_ACTIVITY, BTN_RECOMMENDATIONS],
        [BTN_PARTICIPANTS, BTN_HELP],
    ]


def test_get_main_inline_keyboard():
    keyboard = get_main_inline_keyboard()
    inline_buttons = [
        [(btn.text, btn.callback_data) for btn in row]
        for row in keyboard.inline_keyboard
    ]

    expected = [
        [(BTN_MAP, CB_MAP), (BTN_TIMETABLE, CB_TIMETABLE)],
        [(BTN_CHILDREN_ACTIVITY, CB_CHILDREN_ACTIVITY), (BTN_RECOMMENDATIONS, CB_RECOMMENDATIONS)],
        [(BTN_PARTICIPANTS, CB_PARTICIPANTS), (BTN_HELP, CB_HELP)],
    ]
    assert inline_buttons == expected
