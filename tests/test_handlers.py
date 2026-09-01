"""Unit tests for bot handlers."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram import Update
from telegram.constants import ParseMode

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
async def test_map_handler():
    update = create_mock_update_message("/map")
    context = MagicMock()

    await map_handler(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    kwargs = update.effective_message.reply_text.call_args.kwargs
    assert kwargs["text"] == MAP_MESSAGE
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
@pytest.mark.parametrize(
    "callback_data,expected_text",
    [
        (CB_MAP, MAP_MESSAGE),
        (CB_TIMETABLE, TIMETABLE_MESSAGE),
        (CB_RECOMMENDATIONS, RECOMMENDATIONS_MESSAGE),
        (CB_HELP, HELP_MESSAGE),
    ],
)
async def test_button_callback_handler(callback_data, expected_text):
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
    "button_text,expected_text",
    [
        (BTN_MAP, MAP_MESSAGE),
        ("map", MAP_MESSAGE),
        (BTN_TIMETABLE, TIMETABLE_MESSAGE),
        ("schedule", TIMETABLE_MESSAGE),
        (BTN_RECOMMENDATIONS, RECOMMENDATIONS_MESSAGE),
        ("recs", RECOMMENDATIONS_MESSAGE),
        (BTN_HELP, HELP_MESSAGE),
        ("help", HELP_MESSAGE),
    ],
)
async def test_text_message_handler_known_inputs(button_text, expected_text):
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
    assert "didn't recognize that command" in kwargs["text"]
