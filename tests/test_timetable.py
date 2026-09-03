"""Unit tests for Timetable models, service, keyboards, and section."""

import os
from unittest.mock import AsyncMock, MagicMock
import pytest

from bot.content import CHILDREN_ACTIVITY_MESSAGE, TIMETABLE_MESSAGE
from bot.keyboards import CB_CHILDREN_ACTIVITY, CB_TIMETABLE
from bot.sections.children_activity import ChildrenActivity
from bot.sections.timetable import Timetable
from bot.timetable.day import DayTimetable
from bot.timetable.event import Event
from bot.timetable.keyboards import (
    CB_CA_DATES,
    CB_CA_DATE_PREFIX,
    CB_CA_LOC_PREFIX,
    CB_TT_DATES,
    CB_TT_DATE_PREFIX,
    CB_TT_LOC_PREFIX,
    get_dates_inline_keyboard,
    get_locations_inline_keyboard,
    get_timetable_details_keyboard,
)
from bot.timetable.service import TimetableService


def test_event_from_dict_and_format():
    data = {
        "time": "10:00",
        "title": "Презентация книги",
        "description": "Описание события.",
        "participants": ["Иван Иванов", "Петр Петров"],
        "organizer": "Издательство ABC",
        "location": "Главная сцена",
    }
    event = Event.from_dict(data)
    assert event.time == "10:00"
    assert event.title == "Презентация книги"
    assert event.description == "Описание события."
    assert event.participants == ["Иван Иванов", "Петр Петров"]
    assert event.organizer == "Издательство ABC"
    assert event.location == "Главная сцена"

    md = event.format_markdown()
    assert "⌚ *10:00* — *Презентация книги*" in md
    assert "📝 Описание события." in md
    assert "👥 *Участники:* Иван Иванов, Петр Петров" in md
    assert "📖 *Организатор:* Издательство ABC" in md


def test_day_timetable_from_dict_and_methods():
    day_dict = {
        "date": "13092026",
        "events": [
            {
                "time": "10:00",
                "title": "Событие 1",
                "location": "Сцена 1",
            },
            {
                "time": "11:00",
                "title": "Событие 2",
                "location": "Сцена 2",
            },
            {
                "time": "12:00",
                "title": "Событие 3",
                "location": "Сцена 1",
            },
        ],
    }
    day = DayTimetable.from_dict(day_dict)
    assert day.date == "13092026"
    assert day.format_date_display() == "13.09.2026"
    assert day.get_locations() == ["Сцена 1", "Сцена 2"]

    events_stage1 = day.get_events_for_location("Сцена 1")
    assert len(events_stage1) == 2
    assert events_stage1[0].time == "10:00"
    assert events_stage1[1].time == "12:00"


def test_timetable_service_with_real_assets():
    service = TimetableService()
    dates = service.get_available_dates()
    assert "10092026" in dates
    assert "11092026" in dates
    assert "12092026" in dates
    assert "13092026" in dates
    assert dates == sorted(dates, key=service._get_sort_key)

    day13 = service.get_day("13092026")
    assert day13 is not None
    assert day13.date == "13092026"

    locations = service.get_locations("13092026")
    assert "Сцена" in locations
    assert "Мастер-классы" in locations

    events = service.get_events("13092026", "Сцена")
    assert len(events) >= 2
    assert events[0].time == "10:30"

    formatted = service.format_timetable("13092026", "Сцена")
    assert "13.09.2026" in formatted
    assert "Сцена" in formatted


def test_timetable_keyboards():
    dates = ["10092026", "11092026", "12092026", "13092026"]
    kb_dates = get_dates_inline_keyboard(dates, date_formatter=lambda d: f"{d[:2]}.{d[2:4]}.{d[4:]}")
    assert len(kb_dates.inline_keyboard) == 2  # 2 rows of 2 buttons
    assert kb_dates.inline_keyboard[0][0].callback_data == f"{CB_TT_DATE_PREFIX}10092026"

    locations = ["Главная сцена", "Сцена у Рояля"]
    kb_locs = get_locations_inline_keyboard("13092026", locations)
    assert len(kb_locs.inline_keyboard) == 3  # 2 locations + 1 back button
    assert kb_locs.inline_keyboard[0][0].callback_data == f"{CB_TT_LOC_PREFIX}13092026:0"
    assert kb_locs.inline_keyboard[1][0].callback_data == f"{CB_TT_LOC_PREFIX}13092026:1"
    assert kb_locs.inline_keyboard[2][0].callback_data == CB_TIMETABLE

    kb_details = get_timetable_details_keyboard("13092026")
    assert len(kb_details.inline_keyboard) == 2
    assert kb_details.inline_keyboard[0][0].callback_data == f"{CB_TT_DATE_PREFIX}13092026"
    assert kb_details.inline_keyboard[1][0].callback_data == CB_TIMETABLE


@pytest.mark.asyncio
async def test_timetable_section_interactions():
    section = Timetable()
    assert section.matches_callback(CB_TIMETABLE)
    assert section.matches_callback(CB_TT_DATES)
    assert section.matches_callback("tt_date:13092026")
    assert section.matches_callback("tt_loc:13092026:Главная сцена")
    assert not section.matches_callback("action_map")

    # send_response sends date buttons
    mock_msg = AsyncMock()
    await section.send_response(mock_msg)
    mock_msg.reply_text.assert_awaited_once()
    kwargs = mock_msg.reply_text.call_args.kwargs
    assert kwargs["text"] == TIMETABLE_MESSAGE
    assert kwargs["reply_markup"] is not None

    # handle_callback_query: dates view
    query_dates = AsyncMock()
    query_dates.data = CB_TIMETABLE
    await section.handle_callback_query(query_dates)
    query_dates.edit_message_text.assert_awaited_once()

    # handle_callback_query: locations view
    query_locs = AsyncMock()
    query_locs.data = "tt_date:13092026"
    await section.handle_callback_query(query_locs)
    query_locs.edit_message_text.assert_awaited_once()
    assert "13.09.2026" in query_locs.edit_message_text.call_args.kwargs["text"]

    # handle_callback_query: events view
    query_events = AsyncMock()
    query_events.data = "tt_loc:13092026:0"
    await section.handle_callback_query(query_events)
    query_events.edit_message_text.assert_awaited_once()
    assert "Сцена" in query_events.edit_message_text.call_args.kwargs["text"]


def test_timetable_service_reload_on_each_request(tmp_path):
    import json

    tt_dir = tmp_path / "timetables"
    tt_dir.mkdir()

    file_1 = tt_dir / "01012027.json"
    file_1.write_text(
        json.dumps({
            "date": "01012027",
            "events": [
                {
                    "time": "10:00",
                    "title": "Initial Event",
                    "location": "Room 1",
                }
            ]
        }),
        encoding="utf-8",
    )

    service = TimetableService(timetables_dir=str(tt_dir))
    dates = service.get_available_dates()
    assert dates == ["01012027"]
    events = service.get_events("01012027", "Room 1")
    assert len(events) == 1
    assert events[0].title == "Initial Event"

    # Update file content on disk without restarting or recreating service
    file_1.write_text(
        json.dumps({
            "date": "01012027",
            "events": [
                {
                    "time": "10:00",
                    "title": "Updated Event Title",
                    "location": "Room 1",
                },
                {
                    "time": "12:00",
                    "title": "New Second Event",
                    "location": "Room 2",
                }
            ]
        }),
        encoding="utf-8",
    )

    # Next call must immediately reflect changes
    updated_events = service.get_events("01012027", "Room 1")
    assert len(updated_events) == 1
    assert updated_events[0].title == "Updated Event Title"

    locations = service.get_locations("01012027")
    assert set(locations) == {"Room 1", "Room 2"}

    # Add a new date file
    file_2 = tt_dir / "02012027.json"
    file_2.write_text(
        json.dumps({
            "date": "02012027",
            "events": [
                {
                    "time": "15:00",
                    "title": "Event Day 2",
                    "location": "Room 2",
                }
            ]
        }),
        encoding="utf-8",
    )

    updated_dates = service.get_available_dates()
    assert updated_dates == ["01012027", "02012027"]


def test_children_activity_event_and_day_filtering():
    day_dict = {
        "date": "14092026",
        "events": [
            {
                "time": "10:00",
                "title": "Взрослая лекция",
                "location": "Зал 1",
                "is_children_activity": False,
            },
            {
                "time": "11:30",
                "title": "Детский мастер-класс",
                "location": "Детский уголок",
                "is_children_activity": True,
            },
            {
                "time": "13:00",
                "title": "Сказки для малышей",
                "location": "Детский уголок",
                "is_children_activity": "true",
            },
        ],
    }
    day = DayTimetable.from_dict(day_dict)
    assert len(day.events) == 3
    assert day.events[0].is_children_activity is False
    assert day.events[1].is_children_activity is True
    assert day.events[2].is_children_activity is True

    # Check to_dict preservation
    d1 = day.events[1].to_dict()
    assert d1["is_children_activity"] is True

    # General timetable locations & events: returns ALL events
    all_locs = day.get_locations(children_only=False)
    assert all_locs == ["Зал 1", "Детский уголок"]
    all_kids_loc_events = day.get_events_for_location("Детский уголок", children_only=False)
    assert len(all_kids_loc_events) == 2

    # Children-only filtering: returns only locations and events with is_children_activity=True
    ca_locs = day.get_locations(children_only=True)
    assert ca_locs == ["Детский уголок"]
    ca_events = day.get_events_for_location("Детский уголок", children_only=True)
    assert len(ca_events) == 2
    assert day.get_events_for_location("Зал 1", children_only=True) == []


@pytest.mark.asyncio
async def test_children_activity_section_interactions():
    section = ChildrenActivity()
    assert section.matches_callback(CB_CHILDREN_ACTIVITY)
    assert section.matches_callback(CB_CA_DATES)
    assert section.matches_callback("ca_date:13092026")
    assert section.matches_callback("ca_loc:13092026:Сцена у Рояля")
    assert not section.matches_callback(CB_TIMETABLE)

    # send_response sends date buttons
    mock_msg = AsyncMock()
    await section.send_response(mock_msg)
    mock_msg.reply_text.assert_awaited_once()
    kwargs = mock_msg.reply_text.call_args.kwargs
    assert kwargs["text"] == CHILDREN_ACTIVITY_MESSAGE
    assert kwargs["reply_markup"] is not None

    # handle_callback_query: dates view
    query_dates = AsyncMock()
    query_dates.data = CB_CHILDREN_ACTIVITY
    await section.handle_callback_query(query_dates)
    query_dates.edit_message_text.assert_awaited_once()

    # handle_callback_query: locations view
    query_locs = AsyncMock()
    query_locs.data = "ca_date:13092026"
    await section.handle_callback_query(query_locs)
    query_locs.edit_message_text.assert_awaited_once()

    # handle_callback_query: events view
    query_events = AsyncMock()
    query_events.data = "ca_loc:13092026:Сцена у Рояля"
    await section.handle_callback_query(query_events)
    query_events.edit_message_text.assert_awaited_once()
    assert "Детская программа" in query_events.edit_message_text.call_args.kwargs["text"]


def test_events_sorted_by_time_then_name():
    """Verify events are sorted chronologically by time, then alphabetically by title."""
    day_dict = {
        "date": "10092026",
        "events": [
            {"time": "15:00", "title": "Обед с Пидиди"},
            {"time": "10:00", "title": "Презентация книги Четверг"},
            {"time": "09:30", "title": "Биография Майкла Джексона"},
            {"time": "10:00", "title": "Анонс фестиваля"},
            {"time": "20:00", "title": "Кино с Окси"},
            {"time": "10:15", "title": "Мастер-класс"},
        ],
    }
    day = DayTimetable.from_dict(day_dict)
    titles = [e.title for e in day.events]
    times = [e.time for e in day.events]

    assert times == ["09:30", "10:00", "10:00", "10:15", "15:00", "20:00"]
    assert titles == [
        "Биография Майкла Джексона",
        "Анонс фестиваля",
        "Презентация книги Четверг",
        "Мастер-класс",
        "Обед с Пидиди",
        "Кино с Окси",
    ]


@pytest.mark.asyncio
async def test_long_location_name_callback_under_64_bytes():
    """Ensure dynamic location keyboards do not exceed Telegram's 64-byte callback_data limit."""
    long_location = "Spojka Events, Pernerova 697/35, Praha 8 (Мастер-классы и интерактивные презентации)"
    # Raw location in UTF-8 would easily exceed 64 bytes
    assert len(f"tt_loc:13092026:{long_location}".encode("utf-8")) > 64

    kb = get_locations_inline_keyboard("13092026", [long_location])
    for row in kb.inline_keyboard:
        for btn in row:
            assert len(btn.callback_data.encode("utf-8")) <= 64

    # Verify clicking the button resolves the full long location
    service = TimetableService()
    section = Timetable(service=service)
    # Mock get_locations to return long_location
    section.service.get_locations = lambda d: [long_location]
    section.service.format_timetable = lambda d, loc: f"Schedule for {loc}"

    query = AsyncMock()
    query.data = kb.inline_keyboard[0][0].callback_data  # "tt_loc:13092026:0"
    query.edit_message_text = AsyncMock()

    await section.handle_callback_query(query)
    query.edit_message_text.assert_awaited_once()
    assert long_location in query.edit_message_text.call_args.kwargs["text"]
