"""Tests for keyboard layout builders."""

from bot.content import (
    BTN_BACK_TO_MAP,
    BTN_CHILDREN_ACTIVITY,
    BTN_HELP,
    BTN_MAP,
    BTN_PARTICIPANTS,
    BTN_RECOMMENDATIONS,
    BTN_SHOW_PARTICIPANTS,
    BTN_SHOW_STANDS,
    BTN_TIMETABLE,
    BUTTON_CALLBACK_MAP,
    CB_CHILDREN_ACTIVITY,
    CB_HELP,
    CB_MAP,
    CB_PARTICIPANTS,
    CB_RECOMMENDATIONS,
    CB_STANDS,
    CB_STAND_PREFIX,
    CB_TIMETABLE,
)
from bot.keyboards import (
    get_main_inline_keyboard,
    get_main_reply_keyboard,
    get_map_inline_keyboard,
    get_stands_grid_inline_keyboard,
)
from bot.participants.keyboards import (
    BTN_BACK_TO_PARTICIPANTS,
    PARTICIPANTS_CALLBACK_MAP,
    get_participant_details_keyboard,
    get_stand_participants_inline_keyboard,
)
from bot.participants.participant import Participant
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
    assert btn.text == BTN_SHOW_STANDS
    assert btn.callback_data == CB_STANDS
    assert btn.callback_data != btn.text
    assert BUTTON_CALLBACK_MAP[btn.text] == btn.callback_data


def test_get_stands_grid_inline_keyboard():
    # Test with custom stands list
    stands = ["1", "2", "3", "4", "5", "A-1"]
    keyboard = get_stands_grid_inline_keyboard(stands=stands, columns=4)
    assert len(keyboard.inline_keyboard) == 2  # 4 in first row, 2 in second row
    assert len(keyboard.inline_keyboard[0]) == 4
    assert len(keyboard.inline_keyboard[1]) == 2

    assert keyboard.inline_keyboard[0][0].text == "1"
    assert keyboard.inline_keyboard[0][0].callback_data == f"{CB_STAND_PREFIX}0"
    assert keyboard.inline_keyboard[0][3].text == "4"
    assert keyboard.inline_keyboard[0][3].callback_data == f"{CB_STAND_PREFIX}3"
    assert keyboard.inline_keyboard[1][0].text == "5"
    assert keyboard.inline_keyboard[1][0].callback_data == f"{CB_STAND_PREFIX}4"
    assert keyboard.inline_keyboard[1][1].text == "A-1"
    assert keyboard.inline_keyboard[1][1].callback_data == f"{CB_STAND_PREFIX}5"

    # Test default loading from ParticipantsService
    default_kb = get_stands_grid_inline_keyboard()
    assert len(default_kb.inline_keyboard) > 0
    for row in default_kb.inline_keyboard:
        for btn in row:
            assert btn.callback_data.startswith(CB_STAND_PREFIX)


def test_get_stand_participants_inline_keyboard():
    p1 = Participant(name="Издательство А", stand="1")
    p2 = Participant(name="Издательство Б", stand="1")
    all_parts = [p1, p2]

    kb = get_stand_participants_inline_keyboard([p1, p2], all_participants=all_parts, stand_key="0")
    assert len(kb.inline_keyboard) == 3  # 2 participant buttons + 1 back to map button

    assert p1.name in kb.inline_keyboard[0][0].text
    assert kb.inline_keyboard[0][0].callback_data == "part_item:0:s:0"
    assert p2.name in kb.inline_keyboard[1][0].text
    assert kb.inline_keyboard[1][0].callback_data == "part_item:1:s:0"

    back_btn = kb.inline_keyboard[2][0]
    assert back_btn.text == BTN_BACK_TO_MAP
    assert back_btn.callback_data == CB_MAP


def test_submodule_inline_keyboards_callback_maps():
    # Participants navigation (global)
    part_kb = get_participant_details_keyboard()
    part_btn = part_kb.inline_keyboard[0][0]
    assert part_btn.text == BTN_BACK_TO_PARTICIPANTS
    assert part_btn.callback_data == PARTICIPANTS_CALLBACK_MAP[BTN_BACK_TO_PARTICIPANTS]
    assert part_btn.callback_data != part_btn.text

    # Participants navigation (from stand)
    stand_part_kb = get_participant_details_keyboard(stand_key="0")
    stand_part_btn = stand_part_kb.inline_keyboard[0][0]
    assert stand_part_btn.text == BTN_BACK_TO_PARTICIPANTS
    assert stand_part_btn.callback_data == f"{CB_STAND_PREFIX}0"

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
