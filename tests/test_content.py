"""Tests for bot content and messages."""

from bot.content import (
    BTN_HELP,
    BTN_MAP,
    BTN_RECOMMENDATIONS,
    BTN_TIMETABLE,
    HELP_MESSAGE,
    MAP_IMAGE_PATH,
    MAP_MESSAGE,
    MAP_PATH,
    RECOMMENDATIONS_MESSAGE,
    START_MESSAGE,
    TIMETABLE_MESSAGE,
    UNKNOWN_COMMAND_MESSAGE,
)


def test_start_message_contains_commands_and_intro():
    assert "BookTowerBot" in START_MESSAGE
    assert "/map" in START_MESSAGE
    assert "/timetable" in START_MESSAGE
    assert "/recommendations" in START_MESSAGE
    assert "/help" in START_MESSAGE


def test_help_message_contains_all_command_references():
    assert "/start" in HELP_MESSAGE
    assert "/map" in HELP_MESSAGE
    assert "/timetable" in HELP_MESSAGE
    assert "/recommendations" in HELP_MESSAGE
    assert "/help" in HELP_MESSAGE


def test_map_message_contains_venue_details():
    assert "План" in MAP_MESSAGE or "Карта" in MAP_MESSAGE
    assert "Павильон A" in MAP_MESSAGE
    assert "Павильон B" in MAP_MESSAGE
    assert "Главная сцена" in MAP_MESSAGE


def test_timetable_message_contains_schedule_entries():
    assert "Расписание" in TIMETABLE_MESSAGE
    assert "10:00" in TIMETABLE_MESSAGE
    assert "Главная сцена" in TIMETABLE_MESSAGE


def test_recommendations_message_contains_picks():
    assert "Рекомендации" in RECOMMENDATIONS_MESSAGE
    assert "Стенд" in RECOMMENDATIONS_MESSAGE


def test_map_image_path_defined():
    assert isinstance(MAP_IMAGE_PATH, str) and len(MAP_IMAGE_PATH) > 0
    assert MAP_IMAGE_PATH.endswith(".png")
    assert MAP_PATH == MAP_IMAGE_PATH


def test_button_constants():
    assert isinstance(BTN_MAP, str) and len(BTN_MAP) > 0
    assert isinstance(BTN_TIMETABLE, str) and len(BTN_TIMETABLE) > 0
    assert isinstance(BTN_RECOMMENDATIONS, str) and len(BTN_RECOMMENDATIONS) > 0
    assert isinstance(BTN_HELP, str) and len(BTN_HELP) > 0
    assert isinstance(UNKNOWN_COMMAND_MESSAGE, str) and len(UNKNOWN_COMMAND_MESSAGE) > 0
