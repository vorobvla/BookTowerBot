"""Tests for bot content and messages."""

from bot.content import (
    BTN_HELP,
    BTN_MAP,
    BTN_RECOMMENDATIONS,
    BTN_TIMETABLE,
    HELP_MESSAGE,
    MAP_MESSAGE,
    RECOMMENDATIONS_MESSAGE,
    START_MESSAGE,
    TIMETABLE_MESSAGE,
)


def test_start_message_contains_commands_and_intro():
    assert "Welcome to BookTowerBot" in START_MESSAGE
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
    assert "Venue Map" in MAP_MESSAGE
    assert "Pavilion A" in MAP_MESSAGE
    assert "Pavilion B" in MAP_MESSAGE
    assert "Main Stage" in MAP_MESSAGE


def test_timetable_message_contains_schedule_entries():
    assert "Timetable" in TIMETABLE_MESSAGE
    assert "10:00" in TIMETABLE_MESSAGE
    assert "Main Stage" in TIMETABLE_MESSAGE


def test_recommendations_message_contains_picks():
    assert "Recommendations" in RECOMMENDATIONS_MESSAGE
    assert "Must-Visit Booths" in RECOMMENDATIONS_MESSAGE
    assert "Featured Book Picks" in RECOMMENDATIONS_MESSAGE


def test_button_constants():
    assert isinstance(BTN_MAP, str) and len(BTN_MAP) > 0
    assert isinstance(BTN_TIMETABLE, str) and len(BTN_TIMETABLE) > 0
    assert isinstance(BTN_RECOMMENDATIONS, str) and len(BTN_RECOMMENDATIONS) > 0
    assert isinstance(BTN_HELP, str) and len(BTN_HELP) > 0
