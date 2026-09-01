"""Tests for bot content and messages."""

from bot.content import (
    BTN_HELP,
    BTN_MAP,
    BTN_RECOMMENDATIONS,
    BTN_TIMETABLE,
    HELP_MESSAGE,
    MAP_MESSAGE,
    MAP_PATH,
    RECOMMENDATIONS_MESSAGE,
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
    assert "/help" in START_MESSAGE


def test_help_message_contains_all_command_references():
    assert "/start" in HELP_MESSAGE
    assert "/map" in HELP_MESSAGE
    assert "/timetables" in HELP_MESSAGE
    assert "/recommendations" in HELP_MESSAGE
    assert "/help" in HELP_MESSAGE


def test_map_message_defined():
    assert isinstance(MAP_MESSAGE, str)


def test_timetable_message_contains_schedule_prompt():
    assert "Расписание" in TIMETABLE_MESSAGE
    assert "дату" in TIMETABLE_MESSAGE.lower() or "выберите" in TIMETABLE_MESSAGE.lower()


def test_timetables_path_defined():
    assert isinstance(TIMETABLES_PATH, str) and len(TIMETABLES_PATH) > 0


def test_recommendations_message_contains_picks():
    assert "Рекомендации" in RECOMMENDATIONS_MESSAGE
    assert "Стенд" in RECOMMENDATIONS_MESSAGE


def test_map_path_defined():
    assert isinstance(MAP_PATH, str) and len(MAP_PATH) > 0
    assert MAP_PATH.endswith(".png")


def test_button_constants():
    assert isinstance(BTN_MAP, str) and len(BTN_MAP) > 0
    assert isinstance(BTN_TIMETABLE, str) and len(BTN_TIMETABLE) > 0
    assert isinstance(BTN_RECOMMENDATIONS, str) and len(BTN_RECOMMENDATIONS) > 0
    assert isinstance(BTN_HELP, str) and len(BTN_HELP) > 0
    assert isinstance(UNKNOWN_COMMAND_MESSAGE, str) and len(UNKNOWN_COMMAND_MESSAGE) > 0
