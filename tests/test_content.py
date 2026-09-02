"""Tests for bot content and messages."""

from bot.content import (
    BTN_HELP,
    BTN_MAP,
    BTN_PARTICIPANTS,
    BTN_RECOMMENDATIONS,
    BTN_TIMETABLE,
    HELP_MESSAGE,
    MAP_MESSAGE,
    MAP_PATH,
    MAP_UNAVAILABLE_MESSAGE,
    PARTICIPANTS_MESSAGE,
    PARTICIPANTS_PATH,
    RECOMMENDATIONS_MESSAGE,
    RECS_PATH,
    START_MESSAGE,
    TIMETABLE_MESSAGE,
    TIMETABLES_PATH,
    UNKNOWN_COMMAND_MESSAGE,
)


def test_start_message_contains_commands_and_intro():
    assert "BookTowerBot" in START_MESSAGE
    assert "/map" in START_MESSAGE
    assert "/timetables" in START_MESSAGE
    assert "/recommendations" in START_MESSAGE
    assert "/participants" in START_MESSAGE
    assert "/help" in START_MESSAGE


def test_help_message_contains_all_command_references():
    assert "/start" in HELP_MESSAGE
    assert "/map" in HELP_MESSAGE
    assert "/timetables" in HELP_MESSAGE
    assert "/recommendations" in HELP_MESSAGE
    assert "/participants" in HELP_MESSAGE
    assert "/help" in HELP_MESSAGE


def test_map_message_defined():
    assert isinstance(MAP_MESSAGE, str)


def test_map_unavailable_message_defined():
    assert isinstance(MAP_UNAVAILABLE_MESSAGE, str) and len(MAP_UNAVAILABLE_MESSAGE) > 0
    assert "недоступна" in MAP_UNAVAILABLE_MESSAGE.lower() or "карта" in MAP_UNAVAILABLE_MESSAGE.lower()


def test_timetable_message_contains_schedule_prompt():
    assert "Расписание" in TIMETABLE_MESSAGE
    assert "дату" in TIMETABLE_MESSAGE.lower() or "выберите" in TIMETABLE_MESSAGE.lower()


def test_timetables_path_defined():
    assert isinstance(TIMETABLES_PATH, str) and len(TIMETABLES_PATH) > 0


def test_recommendations_message_contains_prompt():
    assert "Рекомендации" in RECOMMENDATIONS_MESSAGE


def test_participants_message_contains_prompt():
    assert "Участники" in PARTICIPANTS_MESSAGE


def test_participants_path_defined():
    assert isinstance(PARTICIPANTS_PATH, str) and len(PARTICIPANTS_PATH) > 0
    assert PARTICIPANTS_PATH.endswith(".json")


def test_recs_path_defined():
    assert isinstance(RECS_PATH, str) and len(RECS_PATH) > 0
    assert RECS_PATH.endswith(".json")


def test_map_path_defined():
    assert isinstance(MAP_PATH, str) and len(MAP_PATH) > 0
    assert MAP_PATH.endswith(".png")


def test_button_constants():
    assert isinstance(BTN_MAP, str) and len(BTN_MAP) > 0
    assert isinstance(BTN_TIMETABLE, str) and len(BTN_TIMETABLE) > 0
    assert isinstance(BTN_RECOMMENDATIONS, str) and len(BTN_RECOMMENDATIONS) > 0
    assert isinstance(BTN_PARTICIPANTS, str) and len(BTN_PARTICIPANTS) > 0
    assert isinstance(BTN_HELP, str) and len(BTN_HELP) > 0
    assert isinstance(UNKNOWN_COMMAND_MESSAGE, str) and len(UNKNOWN_COMMAND_MESSAGE) > 0
