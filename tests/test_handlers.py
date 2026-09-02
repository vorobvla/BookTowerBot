"""Unit tests for bot handlers."""

import os
from unittest.mock import AsyncMock, MagicMock, mock_open, patch
import pytest
from telegram import Update
from telegram.constants import ParseMode

from bot.content import (
    BTN_CHILDREN_ACTIVITY,
    BTN_HELP,
    BTN_MAP,
    BTN_PARTICIPANTS,
    BTN_RECOMMENDATIONS,
    BTN_TIMETABLE,
    CHILDREN_ACTIVITY_MESSAGE,
    HELP_MESSAGE,
    MAP_MESSAGE,
    PARTICIPANTS_MESSAGE,
    RECOMMENDATIONS_MESSAGE,
    START_MESSAGE,
    TIMETABLE_MESSAGE,
    UNKNOWN_COMMAND_MESSAGE,
)
from bot.handlers import (
    button_callback_handler,
    children_activity_handler,
    help_handler,
    map_handler,
    participants_handler,
    recommendations_handler,
    start_handler,
    text_message_handler,
    timetable_handler,
)
from bot.keyboards import (
    CB_CHILDREN_ACTIVITY,
    CB_HELP,
    CB_MAP,
    CB_PARTICIPANTS,
    CB_RECOMMENDATIONS,
    CB_TIMETABLE,
)


def create_mock_update_message(text: str = "") -> Update:
    """Helper to create a mocked Update object with effective_message."""
    update = MagicMock(spec=Update)
    message = AsyncMock()
    message.text = text
    message.reply_text = AsyncMock()
    message.reply_photo = AsyncMock()
    update.effective_message = message
    update.callback_query = None
    return update


def create_mock_update_callback(callback_data: str) -> Update:
    """Helper to create a mocked Update object with callback_query."""
    update = MagicMock(spec=Update)
    update.effective_message = None
    query = AsyncMock()
    query.data = callback_data
    query.answer = AsyncMock()
    query.message = AsyncMock()
    query.message.reply_text = AsyncMock()
    query.message.reply_photo = AsyncMock()
    update.callback_query = query
    return update


@pytest.mark.asyncio
async def test_start_handler():
    update = create_mock_update_message("/start")
    context = MagicMock()

    await start_handler(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    kwargs = update.effective_message.reply_text.call_args.kwargs
    assert kwargs["text"] == START_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN
    assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_help_handler():
    update = create_mock_update_message("/help")
    context = MagicMock()

    await help_handler(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    kwargs = update.effective_message.reply_text.call_args.kwargs
    assert kwargs["text"] == HELP_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_map_handler_returns_photo():
    update = create_mock_update_message("/map")
    context = MagicMock()

    await map_handler(update, context)

    update.effective_message.reply_photo.assert_awaited_once()
    kwargs = update.effective_message.reply_photo.call_args.kwargs
    assert kwargs["caption"] == MAP_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN
    assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_map_handler_with_existing_file():
    update = create_mock_update_message("/map")
    context = MagicMock()

    m_open = mock_open(read_data=b"fake_png_data")
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open):
        await map_handler(update, context)

    update.effective_message.reply_photo.assert_awaited_once()
    kwargs = update.effective_message.reply_photo.call_args.kwargs
    assert kwargs["caption"] == MAP_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_button_callback_handler_map_with_existing_file():
    update = create_mock_update_callback(CB_MAP)
    context = MagicMock()

    m_open = mock_open(read_data=b"fake_png_data")
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open):
        await button_callback_handler(update, context)

    update.callback_query.answer.assert_awaited_once()
    update.callback_query.message.reply_photo.assert_awaited_once()
    kwargs = update.callback_query.message.reply_photo.call_args.kwargs
    assert kwargs["caption"] == MAP_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_timetable_handler():
    update = create_mock_update_message("/timetables")
    context = MagicMock()

    await timetable_handler(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    kwargs = update.effective_message.reply_text.call_args.kwargs
    assert kwargs["text"] == TIMETABLE_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_children_activity_handler():
    update = create_mock_update_message("/children")
    context = MagicMock()

    await children_activity_handler(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    kwargs = update.effective_message.reply_text.call_args.kwargs
    assert kwargs["text"] == CHILDREN_ACTIVITY_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_recommendations_handler():
    update = create_mock_update_message("/recommendations")
    context = MagicMock()

    await recommendations_handler(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    kwargs = update.effective_message.reply_text.call_args.kwargs
    assert kwargs["text"] == RECOMMENDATIONS_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_participants_handler():
    update = create_mock_update_message("/participants")
    context = MagicMock()

    await participants_handler(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    kwargs = update.effective_message.reply_text.call_args.kwargs
    assert kwargs["text"] == PARTICIPANTS_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_button_callback_handler_map():
    update = create_mock_update_callback(CB_MAP)
    context = MagicMock()

    await button_callback_handler(update, context)

    update.callback_query.answer.assert_awaited_once()
    update.callback_query.message.reply_photo.assert_awaited_once()
    kwargs = update.callback_query.message.reply_photo.call_args.kwargs
    assert kwargs["caption"] == MAP_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_button_callback_handler_help():
    update = create_mock_update_callback(CB_HELP)
    context = MagicMock()

    await button_callback_handler(update, context)

    update.callback_query.answer.assert_awaited_once()
    update.callback_query.message.reply_text.assert_awaited_once()
    kwargs = update.callback_query.message.reply_text.call_args.kwargs
    assert kwargs["text"] == HELP_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_button_callback_handler_recommendations_flow():
    # 1. Click recommendations -> returns category buttons
    update_recs = create_mock_update_callback(CB_RECOMMENDATIONS)
    context = MagicMock()
    await button_callback_handler(update_recs, context)
    update_recs.callback_query.answer.assert_awaited_once()
    update_recs.callback_query.edit_message_text.assert_awaited_once()
    kwargs_recs = update_recs.callback_query.edit_message_text.call_args.kwargs
    assert kwargs_recs["text"] == RECOMMENDATIONS_MESSAGE
    assert kwargs_recs["reply_markup"] is not None

    # 2. Click category button -> returns books
    update_cat = create_mock_update_callback("rec_cat:Нонфикшн")
    await button_callback_handler(update_cat, context)
    update_cat.callback_query.answer.assert_awaited_once()
    update_cat.callback_query.edit_message_text.assert_awaited_once()
    kwargs_cat = update_cat.callback_query.edit_message_text.call_args.kwargs
    assert "Нонфикшн" in kwargs_cat["text"]
    assert "Книга Жопова" in kwargs_cat["text"]
    assert kwargs_cat["reply_markup"] is not None


@pytest.mark.asyncio
async def test_button_callback_handler_participants_flow():
    # 1. Click participants -> returns list of participants
    update_parts = create_mock_update_callback(CB_PARTICIPANTS)
    context = MagicMock()
    await button_callback_handler(update_parts, context)
    update_parts.callback_query.answer.assert_awaited_once()
    update_parts.callback_query.edit_message_text.assert_awaited_once()
    kwargs_parts = update_parts.callback_query.edit_message_text.call_args.kwargs
    assert kwargs_parts["text"] == PARTICIPANTS_MESSAGE
    assert kwargs_parts["reply_markup"] is not None

    # 2. Click participant item -> returns details
    update_item = create_mock_update_callback("part_item:0")
    await button_callback_handler(update_item, context)
    update_item.callback_query.answer.assert_awaited_once()
    update_item.callback_query.edit_message_text.assert_awaited_once()
    kwargs_item = update_item.callback_query.edit_message_text.call_args.kwargs
    assert kwargs_item["reply_markup"] is not None


@pytest.mark.asyncio
async def test_button_callback_handler_timetable_flow():
    # 1. Click timetable action -> returns dates
    update_dates = create_mock_update_callback(CB_TIMETABLE)
    context = MagicMock()
    await button_callback_handler(update_dates, context)
    update_dates.callback_query.answer.assert_awaited_once()
    update_dates.callback_query.edit_message_text.assert_awaited_once()
    kwargs_dates = update_dates.callback_query.edit_message_text.call_args.kwargs
    assert kwargs_dates["text"] == TIMETABLE_MESSAGE
    assert kwargs_dates["reply_markup"] is not None

    # 2. Click a date -> returns locations for that day
    update_locs = create_mock_update_callback("tt_date:13092026")
    await button_callback_handler(update_locs, context)
    update_locs.callback_query.answer.assert_awaited_once()
    update_locs.callback_query.edit_message_text.assert_awaited_once()
    kwargs_locs = update_locs.callback_query.edit_message_text.call_args.kwargs
    assert "13.09.2026" in kwargs_locs["text"]
    assert kwargs_locs["reply_markup"] is not None

    # 3. Click a location -> returns events for that location
    update_events = create_mock_update_callback("tt_loc:13092026:Главная сцена")
    await button_callback_handler(update_events, context)
    update_events.callback_query.answer.assert_awaited_once()
    update_events.callback_query.edit_message_text.assert_awaited_once()
    kwargs_events = update_events.callback_query.edit_message_text.call_args.kwargs
    assert "Главная сцена" in kwargs_events["text"]
    assert "13.09.2026" in kwargs_events["text"]
    assert "10:00" in kwargs_events["text"]
    assert kwargs_events["reply_markup"] is not None


@pytest.mark.asyncio
async def test_button_callback_handler_children_activity_flow():
    # 1. Click children activity action -> returns dates
    update_dates = create_mock_update_callback(CB_CHILDREN_ACTIVITY)
    context = MagicMock()
    await button_callback_handler(update_dates, context)
    update_dates.callback_query.answer.assert_awaited_once()
    update_dates.callback_query.edit_message_text.assert_awaited_once()
    kwargs_dates = update_dates.callback_query.edit_message_text.call_args.kwargs
    assert kwargs_dates["text"] == CHILDREN_ACTIVITY_MESSAGE
    assert kwargs_dates["reply_markup"] is not None

    # 2. Click a date -> returns locations for that day
    update_locs = create_mock_update_callback("ca_date:13092026")
    await button_callback_handler(update_locs, context)
    update_locs.callback_query.answer.assert_awaited_once()
    update_locs.callback_query.edit_message_text.assert_awaited_once()
    kwargs_locs = update_locs.callback_query.edit_message_text.call_args.kwargs
    assert kwargs_locs["reply_markup"] is not None

    # 3. Click a location -> returns events for that location
    update_events = create_mock_update_callback("ca_loc:13092026:Сцена у Рояля")
    await button_callback_handler(update_events, context)
    update_events.callback_query.answer.assert_awaited_once()
    update_events.callback_query.edit_message_text.assert_awaited_once()
    kwargs_events = update_events.callback_query.edit_message_text.call_args.kwargs
    assert "Детская программа" in kwargs_events["text"]
    assert kwargs_events["reply_markup"] is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "button_text",
    [
        BTN_MAP,
        "map",
        "план",
        "карта",
        "схема",
    ],
)
async def test_text_message_handler_map_inputs(button_text):
    update = create_mock_update_message(button_text)
    context = MagicMock()

    await text_message_handler(update, context)

    update.effective_message.reply_photo.assert_awaited_once()
    kwargs = update.effective_message.reply_photo.call_args.kwargs
    assert kwargs["caption"] == MAP_MESSAGE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "button_text,expected_text",
    [
        (BTN_TIMETABLE, TIMETABLE_MESSAGE),
        ("schedule", TIMETABLE_MESSAGE),
        ("расписание", TIMETABLE_MESSAGE),
        ("программа", TIMETABLE_MESSAGE),
        (BTN_CHILDREN_ACTIVITY, CHILDREN_ACTIVITY_MESSAGE),
        ("детская программа", CHILDREN_ACTIVITY_MESSAGE),
        ("дети", CHILDREN_ACTIVITY_MESSAGE),
        (BTN_RECOMMENDATIONS, RECOMMENDATIONS_MESSAGE),
        ("recs", RECOMMENDATIONS_MESSAGE),
        ("рекомендации", RECOMMENDATIONS_MESSAGE),
        (BTN_PARTICIPANTS, PARTICIPANTS_MESSAGE),
        ("participants", PARTICIPANTS_MESSAGE),
        ("участники", PARTICIPANTS_MESSAGE),
        ("стенды", PARTICIPANTS_MESSAGE),
        (BTN_HELP, HELP_MESSAGE),
        ("help", HELP_MESSAGE),
        ("помощь", HELP_MESSAGE),
        ("справка", HELP_MESSAGE),
    ],
)
async def test_text_message_handler_known_text_inputs(button_text, expected_text):
    update = create_mock_update_message(button_text)
    context = MagicMock()

    await text_message_handler(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    kwargs = update.effective_message.reply_text.call_args.kwargs
    assert kwargs["text"] == expected_text


@pytest.mark.asyncio
async def test_text_message_handler_unknown_input():
    update = create_mock_update_message("random unknown query")
    context = MagicMock()

    await text_message_handler(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    kwargs = update.effective_message.reply_text.call_args.kwargs
    assert kwargs["text"] == UNKNOWN_COMMAND_MESSAGE
