"""Unit tests for bot handlers."""

import os
from unittest.mock import AsyncMock, MagicMock, mock_open, patch
import pytest
from telegram import Update
from telegram.constants import ParseMode

from bot.content import (
    BTN_HELP,
    BTN_MAP,
    BTN_RECOMMENDATIONS,
    BTN_TIMETABLE,
    HELP_MESSAGE,
    MAP_IMAGE_PATH,
    MAP_MESSAGE,
    RECOMMENDATIONS_MESSAGE,
    START_MESSAGE,
    TIMETABLE_MESSAGE,
    UNKNOWN_COMMAND_MESSAGE,
)
from bot.handlers import (
    button_callback_handler,
    help_handler,
    map_handler,
    recommendations_handler,
    start_handler,
    text_message_handler,
    timetable_handler,
)
from bot.keyboards import (
    CB_HELP,
    CB_MAP,
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
    update = create_mock_update_message("/timetable")
    context = MagicMock()

    await timetable_handler(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    kwargs = update.effective_message.reply_text.call_args.kwargs
    assert kwargs["text"] == TIMETABLE_MESSAGE
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
@pytest.mark.parametrize(
    "callback_data,expected_text",
    [
        (CB_TIMETABLE, TIMETABLE_MESSAGE),
        (CB_RECOMMENDATIONS, RECOMMENDATIONS_MESSAGE),
        (CB_HELP, HELP_MESSAGE),
    ],
)
async def test_button_callback_handler_text_actions(callback_data, expected_text):
    update = create_mock_update_callback(callback_data)
    context = MagicMock()

    await button_callback_handler(update, context)

    update.callback_query.answer.assert_awaited_once()
    update.callback_query.message.reply_text.assert_awaited_once()
    kwargs = update.callback_query.message.reply_text.call_args.kwargs
    assert kwargs["text"] == expected_text
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN


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
        (BTN_RECOMMENDATIONS, RECOMMENDATIONS_MESSAGE),
        ("recs", RECOMMENDATIONS_MESSAGE),
        ("рекомендации", RECOMMENDATIONS_MESSAGE),
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
