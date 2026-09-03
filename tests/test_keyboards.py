"""Tests for keyboard layout builders."""

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
from bot.keyboards import (
    get_main_inline_keyboard,
    get_main_reply_keyboard,
    get_map_inline_keyboard,
)
from bot.participants.keyboards import (
    BTN_BACK_TO_PARTICIPANTS,
    PARTICIPANTS_CALLBACK_MAP,
    get_participant_details_keyboard,
)
from bot.recommendations.keyboards import (
    BTN_OTHER_CATEGORIES,
    RECOMMENDATIONS_CALLBACK_MAP,
    get_recommendation_details_keyboard,
)
from bot.timetable.keyboards import (
    BTN_BACK_TO_DATES,
    BTN_CHOOSE_OTHER_DATE,
    BTN_OTHER_LOCATION,
    TIMETABLE_CALLBACK_MAP,
    get_locations_inline_keyboard,
    get_timetable_details_keyboard,
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

    # Ensure none of the buttons use their text as callback data
    for row in keyboard.inline_keyboard:
        for btn in row:
            assert btn.callback_data != btn.text
            assert BUTTON_CALLBACK_MAP[btn.text] == btn.callback_data


def test_get_map_inline_keyboard():
    keyboard = get_map_inline_keyboard()
    assert len(keyboard.inline_keyboard) == 1
    assert len(keyboard.inline_keyboard[0]) == 1
    btn = keyboard.inline_keyboard[0][0]
    assert btn.text == "📍 Информация о стендах участников"
    assert btn.text == BTN_SHOW_PARTICIPANTS
    assert btn.callback_data == CB_PARTICIPANTS
    assert btn.callback_data != btn.text
    assert BUTTON_CALLBACK_MAP[btn.text] == btn.callback_data


def test_submodule_inline_keyboards_callback_maps():
    # Participants navigation
    part_kb = get_participant_details_keyboard()
    part_btn = part_kb.inline_keyboard[0][0]
    assert part_btn.text == BTN_BACK_TO_PARTICIPANTS
    assert part_btn.callback_data == PARTICIPANTS_CALLBACK_MAP[BTN_BACK_TO_PARTICIPANTS]
    assert part_btn.callback_data != part_btn.text

    # Recommendations navigation
    rec_kb = get_recommendation_details_keyboard()
    rec_btn = rec_kb.inline_keyboard[0][0]
    assert rec_btn.text == BTN_OTHER_CATEGORIES
    assert rec_btn.callback_data == RECOMMENDATIONS_CALLBACK_MAP[BTN_OTHER_CATEGORIES]
    assert rec_btn.callback_data != rec_btn.text

    # Timetable navigation
    loc_kb = get_locations_inline_keyboard("13092026", ["Room 1"])
    back_btn = loc_kb.inline_keyboard[-1][0]
    assert back_btn.text == BTN_BACK_TO_DATES
    assert back_btn.callback_data == TIMETABLE_CALLBACK_MAP[BTN_BACK_TO_DATES]
    assert back_btn.callback_data != back_btn.text

    tt_details_kb = get_timetable_details_keyboard("13092026")
    other_date_btn = tt_details_kb.inline_keyboard[1][0]
    assert other_date_btn.text == BTN_CHOOSE_OTHER_DATE
    assert other_date_btn.callback_data == TIMETABLE_CALLBACK_MAP[BTN_CHOOSE_OTHER_DATE]
    assert other_date_btn.callback_data != other_date_btn.text
