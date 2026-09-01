"""Unit tests for bot sections and SectionRegistry."""

import os
from unittest.mock import AsyncMock, MagicMock, mock_open, patch
import pytest
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
from bot.keyboards import (
    CB_HELP,
    CB_MAP,
    CB_RECOMMENDATIONS,
    CB_TIMETABLE,
)
from bot.sections import (
    BaseSection,
    Help,
    Map,
    Recommendations,
    SectionRegistry,
    Start,
    Timetable,
    default_registry,
)
from bot.sections.base import BaseSection as DirectBaseSection
from bot.sections.help import Help as DirectHelp
from bot.sections.map import Map as DirectMap
from bot.sections.recommendations import Recommendations as DirectRecommendations
from bot.sections.registry import SectionRegistry as DirectSectionRegistry
from bot.sections.start import Start as DirectStart
from bot.sections.timetable import Timetable as DirectTimetable


@pytest.fixture
def mock_message():
    message = AsyncMock()
    message.reply_text = AsyncMock()
    message.reply_photo = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_start_section(mock_message):
    start = Start()
    assert start.name == "start"
    assert start.matches_command("start")
    assert start.matches_command("/start")
    assert start.matches_text("/start")
    assert start.get_text_content() == START_MESSAGE

    await start.send_response(mock_message)
    mock_message.reply_text.assert_awaited_once()
    kwargs = mock_message.reply_text.call_args.kwargs
    assert kwargs["text"] == START_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_help_section(mock_message):
    help_sec = Help()
    assert help_sec.name == "help"
    assert help_sec.matches_command("help")
    assert help_sec.matches_callback(CB_HELP)
    assert help_sec.matches_text(BTN_HELP)
    assert help_sec.matches_text("справка")
    assert help_sec.get_text_content() == HELP_MESSAGE

    await help_sec.send_response(mock_message)
    mock_message.reply_text.assert_awaited_once()
    kwargs = mock_message.reply_text.call_args.kwargs
    assert kwargs["text"] == HELP_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_map_section_photo_dispatch(mock_message):
    map_sec = Map(image_path="test_map.png")
    assert map_sec.name == "map"
    assert map_sec.matches_command("map")
    assert map_sec.matches_callback(CB_MAP)
    assert map_sec.matches_text(BTN_MAP)
    assert map_sec.matches_text("карта")
    assert map_sec.matches_text("план")
    assert map_sec.get_text_content() == MAP_MESSAGE
    assert "test_map.png" in map_sec.get_display_text()

    # Case 1: file does not exist on disk
    with patch("os.path.exists", return_value=False):
        await map_sec.send_response(mock_message)
        mock_message.reply_photo.assert_awaited_once()
        kwargs = mock_message.reply_photo.call_args.kwargs
        assert kwargs["photo"] == "test_map.png"
        assert kwargs["caption"] == MAP_MESSAGE
        assert kwargs["parse_mode"] == ParseMode.MARKDOWN

    # Case 2: file exists on disk
    mock_message.reply_photo.reset_mock()
    m_open = mock_open(read_data=b"fake_png")
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open):
        await map_sec.send_response(mock_message)
        mock_message.reply_photo.assert_awaited_once()
        kwargs = mock_message.reply_photo.call_args.kwargs
        assert kwargs["caption"] == MAP_MESSAGE
        assert kwargs["parse_mode"] == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_map_section_caches_and_reuses_file_id(mock_message):
    map_sec = Map(image_path="test_map.png")
    assert map_sec.cached_file_id is None

    # First send: simulate Telegram returning a Message with PhotoSize
    photo_mock = MagicMock()
    photo_mock.file_id = "telegram_photo_file_id_999"
    sent_msg_mock = MagicMock()
    sent_msg_mock.photo = (photo_mock,)
    mock_message.reply_photo.return_value = sent_msg_mock

    m_open = mock_open(read_data=b"fake_png")
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open) as mocked_open:
        await map_sec.send_response(mock_message)
        assert mocked_open.called
        assert map_sec.cached_file_id == "telegram_photo_file_id_999"

    # Second send: should use cached file_id and NOT open file
    mock_message.reply_photo.reset_mock()
    m_open2 = mock_open(read_data=b"fake_png")
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open2) as mocked_open:
        await map_sec.send_response(mock_message)
        assert not mocked_open.called
        mock_message.reply_photo.assert_awaited_once()
        kwargs = mock_message.reply_photo.call_args.kwargs
        assert kwargs["photo"] == "telegram_photo_file_id_999"
        assert kwargs["caption"] == MAP_MESSAGE


@pytest.mark.asyncio
async def test_map_section_fallback_on_invalid_cached_file_id(mock_message):
    map_sec = Map(image_path="test_map.png", cached_file_id="stale_file_id")

    # When sending with cached_file_id fails, it should fallback to uploading
    def reply_side_effect(**kwargs):
        if kwargs.get("photo") == "stale_file_id":
            raise RuntimeError("Telegram BadRequest: file_id is invalid")
        sent = MagicMock()
        photo = MagicMock()
        photo.file_id = "new_valid_file_id"
        sent.photo = (photo,)
        return sent

    mock_message.reply_photo.side_effect = reply_side_effect

    m_open = mock_open(read_data=b"fake_png")
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open) as mocked_open:
        await map_sec.send_response(mock_message)
        assert mocked_open.called
        assert map_sec.cached_file_id == "new_valid_file_id"


@pytest.mark.asyncio
async def test_map_section_global_cache_sharing(mock_message):
    Map._global_cached_file_id = None
    map1 = Map()
    map2 = Map()
    assert map1.cached_file_id is None
    assert map2.cached_file_id is None

    photo_mock = MagicMock()
    photo_mock.file_id = "shared_plan_file_id_123"
    sent_msg_mock = MagicMock()
    sent_msg_mock.photo = (photo_mock,)
    mock_message.reply_photo.return_value = sent_msg_mock

    m_open = mock_open(read_data=b"fake_plan_bytes")
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open) as mocked_open:
        await map1.send_response(mock_message)
        assert mocked_open.called
        assert map1.cached_file_id == "shared_plan_file_id_123"
        assert map2.cached_file_id == "shared_plan_file_id_123"

    mock_message.reply_photo.reset_mock()
    m_open2 = mock_open(read_data=b"fake_plan_bytes")
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open2) as mocked_open2:
        await map2.send_response(mock_message)
        assert not mocked_open2.called
        mock_message.reply_photo.assert_awaited_once()
        assert mock_message.reply_photo.call_args.kwargs["photo"] == "shared_plan_file_id_123"


@pytest.mark.asyncio
async def test_timetable_section(mock_message):
    tt = Timetable()
    assert tt.name == "timetables"
    assert tt.matches_command("timetables")
    assert tt.matches_callback(CB_TIMETABLE)
    assert tt.matches_text(BTN_TIMETABLE)
    assert tt.matches_text("расписание")
    assert tt.get_text_content() == TIMETABLE_MESSAGE

    await tt.send_response(mock_message)
    mock_message.reply_text.assert_awaited_once()
    kwargs = mock_message.reply_text.call_args.kwargs
    assert kwargs["text"] == TIMETABLE_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_recommendations_section(mock_message):
    recs = Recommendations()
    assert recs.name == "recommendations"
    assert recs.matches_command("recommendations")
    assert recs.matches_command("recs")
    assert recs.matches_callback(CB_RECOMMENDATIONS)
    assert recs.matches_text(BTN_RECOMMENDATIONS)
    assert recs.matches_text("рекомендации")
    assert recs.get_text_content() == RECOMMENDATIONS_MESSAGE

    await recs.send_response(mock_message)
    mock_message.reply_text.assert_awaited_once()
    kwargs = mock_message.reply_text.call_args.kwargs
    assert kwargs["text"] == RECOMMENDATIONS_MESSAGE
    assert kwargs["parse_mode"] == ParseMode.MARKDOWN


def test_section_registry_routing():
    registry = SectionRegistry()

    # Commands
    assert isinstance(registry.find_by_command("start"), Start)
    assert isinstance(registry.find_by_command("/start"), Start)
    assert isinstance(registry.find_by_command("map"), Map)
    assert isinstance(registry.find_by_command("timetables"), Timetable)
    assert isinstance(registry.find_by_command("recs"), Recommendations)
    assert isinstance(registry.find_by_command("help"), Help)
    assert registry.find_by_command("nonexistent") is None

    # Callbacks
    assert isinstance(registry.find_by_callback(CB_MAP), Map)
    assert isinstance(registry.find_by_callback(CB_TIMETABLE), Timetable)
    assert isinstance(registry.find_by_callback(CB_RECOMMENDATIONS), Recommendations)
    assert isinstance(registry.find_by_callback(CB_HELP), Help)
    assert registry.find_by_callback("unknown_cb") is None

    # Text / Aliases / Buttons
    assert isinstance(registry.find_by_text(BTN_MAP), Map)
    assert isinstance(registry.find_by_text("карта"), Map)
    assert isinstance(registry.find_by_text(BTN_TIMETABLE), Timetable)
    assert isinstance(registry.find_by_text("программа"), Timetable)
    assert isinstance(registry.find_by_text(BTN_RECOMMENDATIONS), Recommendations)
    assert isinstance(registry.find_by_text("рекомендации"), Recommendations)
    assert isinstance(registry.find_by_text(BTN_HELP), Help)
    assert isinstance(registry.find_by_text("помощь"), Help)
    assert registry.find_by_text("unrecognized input") is None


def test_one_class_per_module_imports():
    assert BaseSection is DirectBaseSection
    assert Start is DirectStart
    assert Help is DirectHelp
    assert Map is DirectMap
    assert Timetable is DirectTimetable
    assert Recommendations is DirectRecommendations
    assert SectionRegistry is DirectSectionRegistry
