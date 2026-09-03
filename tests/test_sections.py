"""Unit tests for bot sections and SectionRegistry."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, mock_open, patch
import pytest
from telegram.constants import ParseMode

from bot.content import (
    BTN_CHILDREN_ACTIVITY,
    BTN_HELP,
    BTN_MAP,
    BTN_PARTICIPANTS,
    BTN_RECOMMENDATIONS,
    BTN_SHOW_STANDS,
    BTN_TIMETABLE,
    CHILDREN_ACTIVITY_MESSAGE,
    HELP_MESSAGE,
    MAP_MESSAGE,
    MAP_UNAVAILABLE_MESSAGE,
    PARTICIPANTS_MESSAGE,
    RECOMMENDATIONS_MESSAGE,
    START_MESSAGE,
    TIMETABLE_MESSAGE,
)
from bot.keyboards import (
    CB_CHILDREN_ACTIVITY,
    CB_HELP,
    CB_MAP,
    CB_PARTICIPANTS,
    CB_RECOMMENDATIONS,
    CB_STANDS,
    CB_TIMETABLE,
)
from bot.sections import (
    BaseSection,
    ChildrenActivity,
    Help,
    Map,
    Participants,
    Recommendations,
    SectionRegistry,
    Start,
    Timetable,
    default_registry,
)
from bot.sections.base import BaseSection as DirectBaseSection
from bot.sections.children_activity import ChildrenActivity as DirectChildrenActivity
from bot.sections.help import Help as DirectHelp
from bot.sections.map import Map as DirectMap
from bot.sections.participants import Participants as DirectParticipants
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
        mock_message.reply_text.assert_awaited_once()
        kwargs = mock_message.reply_text.call_args.kwargs
        assert kwargs["text"] == MAP_UNAVAILABLE_MESSAGE
        assert kwargs["parse_mode"] == ParseMode.MARKDOWN
        markup = kwargs["reply_markup"]
        assert markup is not None
        assert markup.inline_keyboard[0][0].text == BTN_SHOW_STANDS
        assert markup.inline_keyboard[0][0].callback_data == CB_STANDS

    # Case 2: file exists on disk
    mock_message.reply_photo.reset_mock()
    m_open = mock_open(read_data=b"fake_png")
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open):
        await map_sec.send_response(mock_message)
        mock_message.reply_photo.assert_awaited_once()
        kwargs = mock_message.reply_photo.call_args.kwargs
        assert kwargs["caption"] == MAP_MESSAGE
        assert kwargs["parse_mode"] == ParseMode.MARKDOWN
        markup = kwargs["reply_markup"]
        assert markup is not None
        assert markup.inline_keyboard[0][0].text == BTN_SHOW_STANDS
        assert markup.inline_keyboard[0][0].callback_data == CB_STANDS


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
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open) as mocked_open, patch("bot.participants.service.ParticipantsService.get_stands", return_value=["1"]):
        await map_sec.send_response(mock_message)
        assert mocked_open.called
        assert map_sec.cached_file_id == "telegram_photo_file_id_999"

    # Second send: should use cached file_id and NOT open file
    mock_message.reply_photo.reset_mock()
    m_open2 = mock_open(read_data=b"fake_png")
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open2) as mocked_open, patch("bot.participants.service.ParticipantsService.get_stands", return_value=["1"]):
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
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open) as mocked_open, patch("bot.participants.service.ParticipantsService.get_stands", return_value=["1"]):
        await map_sec.send_response(mock_message)
        assert mocked_open.called
        assert map_sec.cached_file_id == "new_valid_file_id"


@pytest.mark.asyncio
async def test_map_section_global_cache_sharing(mock_message):
    Map.clear_cache()
    map1 = Map(image_path="test_shared_map.png")
    map2 = Map(image_path="test_shared_map.png")
    assert map1.cached_file_id is None
    assert map2.cached_file_id is None

    photo_mock = MagicMock()
    photo_mock.file_id = "shared_plan_file_id_123"
    sent_msg_mock = MagicMock()
    sent_msg_mock.photo = (photo_mock,)
    mock_message.reply_photo.return_value = sent_msg_mock

    m_open = mock_open(read_data=b"fake_plan_bytes")
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open) as mocked_open, patch("bot.participants.service.ParticipantsService.get_stands", return_value=["1"]):
        await map1.send_response(mock_message)
        assert mocked_open.called
        assert map1.cached_file_id == "shared_plan_file_id_123"
        assert map2.cached_file_id == "shared_plan_file_id_123"

    mock_message.reply_photo.reset_mock()
    m_open2 = mock_open(read_data=b"fake_plan_bytes")
    with patch("os.path.exists", return_value=True), patch("builtins.open", m_open2) as mocked_open2, patch("bot.participants.service.ParticipantsService.get_stands", return_value=["1"]):
        await map2.send_response(mock_message)
        assert not mocked_open2.called
        mock_message.reply_photo.assert_awaited_once()
        assert mock_message.reply_photo.call_args.kwargs["photo"] == "shared_plan_file_id_123"


@pytest.mark.asyncio
async def test_map_section_dynamic_active_map_resolution(tmp_path, mock_message):
    map_dir = tmp_path / "map"
    map_dir.mkdir(parents=True, exist_ok=True)
    map1_file = map_dir / "custom_version_1.png"
    map1_file.write_bytes(b"VERSION_1_BYTES")
    map2_file = map_dir / "custom_version_2.png"
    map2_file.write_bytes(b"VERSION_2_BYTES")

    active_meta = map_dir / "active_map.json"
    active_meta.write_text(json.dumps({"active_map": "custom_version_1.png"}), encoding="utf-8")

    with patch("bot.sections.map.MAP_DIR", str(map_dir)):
        Map.clear_cache()
        map_sec = Map()
        assert map_sec.image_path.endswith("custom_version_1.png")

        # Simulate Telegram upload and caching
        photo_mock = MagicMock()
        photo_mock.file_id = "file_id_v1"
        sent_msg_mock = MagicMock()
        sent_msg_mock.photo = (photo_mock,)
        mock_message.reply_photo.return_value = sent_msg_mock

        await map_sec.send_response(mock_message)
        assert map_sec.cached_file_id == "file_id_v1"

        # Now update active map to version 2 (simulating admin action or file change)
        active_meta.write_text(json.dumps({"active_map": "custom_version_2.png"}), encoding="utf-8")

        # The existing singleton instance should dynamically reflect the new active map
        assert map_sec.image_path.endswith("custom_version_2.png")
        # Cached file_id from version 1 is automatically invalidated
        assert map_sec.cached_file_id is None

        photo_mock2 = MagicMock()
        photo_mock2.file_id = "file_id_v2"
        sent_msg_mock2 = MagicMock()
        sent_msg_mock2.photo = (photo_mock2,)
        mock_message.reply_photo.return_value = sent_msg_mock2

        await map_sec.send_response(mock_message)
        assert map_sec.cached_file_id == "file_id_v2"


@pytest.mark.asyncio
async def test_map_section_no_map_available_returns_placeholder(tmp_path, mock_message):
    empty_map_dir = tmp_path / "empty_map"
    empty_map_dir.mkdir(parents=True, exist_ok=True)

    with patch("bot.sections.map.MAP_DIR", str(empty_map_dir)), patch("bot.sections.map.MAP_PATH", str(empty_map_dir / "nonexistent.png")):
        Map.clear_cache()
        map_sec = Map()
        assert map_sec.image_path is None
        assert map_sec.cached_file_id is None
        assert map_sec.get_display_text() == MAP_UNAVAILABLE_MESSAGE

        await map_sec.send_response(mock_message)
        mock_message.reply_photo.assert_not_called()
        mock_message.reply_text.assert_awaited_once()
        kwargs = mock_message.reply_text.call_args.kwargs
        assert kwargs["text"] == MAP_UNAVAILABLE_MESSAGE
        assert kwargs["parse_mode"] == ParseMode.MARKDOWN
        assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_map_section_upload_failure_returns_placeholder(tmp_path, mock_message):
    map_dir = tmp_path / "map_fail"
    map_dir.mkdir(parents=True, exist_ok=True)
    bad_map_file = map_dir / "corrupted.png"
    bad_map_file.write_bytes(b"BAD_IMAGE")
    active_meta = map_dir / "active_map.json"
    active_meta.write_text(json.dumps({"active_map": "corrupted.png"}), encoding="utf-8")

    with patch("bot.sections.map.MAP_DIR", str(map_dir)):
        Map.clear_cache()
        map_sec = Map()
        mock_message.reply_photo.side_effect = Exception("Telegram API upload failed")

        await map_sec.send_response(mock_message)
        mock_message.reply_text.assert_awaited_once()
        kwargs = mock_message.reply_text.call_args.kwargs
        assert kwargs["text"] == MAP_UNAVAILABLE_MESSAGE
        assert kwargs["parse_mode"] == ParseMode.MARKDOWN


@pytest.mark.asyncio
async def test_map_section_mtime_invalidation(tmp_path, mock_message):
    map_dir = tmp_path / "map_mtime"
    map_dir.mkdir(parents=True, exist_ok=True)
    map_file = map_dir / "map.png"
    map_file.write_bytes(b"INITIAL_MAP_CONTENT")

    with patch("bot.sections.map.MAP_DIR", str(map_dir)), patch("bot.sections.map.MAP_PATH", str(map_file)):
        Map.clear_cache()
        map_sec = Map()

        photo_mock = MagicMock()
        photo_mock.file_id = "initial_file_id"
        sent_msg_mock = MagicMock()
        sent_msg_mock.photo = (photo_mock,)
        mock_message.reply_photo.return_value = sent_msg_mock

        await map_sec.send_response(mock_message)
        assert map_sec.cached_file_id == "initial_file_id"

        # Overwrite file with new content and update its mtime
        import time
        new_mtime = time.time() + 10.0
        map_file.write_bytes(b"UPDATED_MAP_CONTENT")
        os.utime(str(map_file), (new_mtime, new_mtime))

        # Cache should now be automatically invalidated because file mtime changed
        assert map_sec.cached_file_id is None

        photo_mock2 = MagicMock()
        photo_mock2.file_id = "updated_file_id"
        sent_msg_mock2 = MagicMock()
        sent_msg_mock2.photo = (photo_mock2,)
        mock_message.reply_photo.return_value = sent_msg_mock2

        await map_sec.send_response(mock_message)
        assert map_sec.cached_file_id == "updated_file_id"


@pytest.mark.asyncio
async def test_map_section_clear_cache_utility():
    Map._global_cached_file_id = "test_id"
    Map._global_cached_image_path = "/path/test.png"
    Map._global_cached_mtime = 12345.0

    Map.clear_cache()
    assert Map._global_cached_file_id is None
    assert Map._global_cached_image_path is None
    assert Map._global_cached_mtime is None


def test_map_section_get_reply_markup():
    map_sec = Map()
    inline_markup = map_sec.get_reply_markup(inline=True)
    assert inline_markup is not None
    assert len(inline_markup.inline_keyboard) == 1
    assert inline_markup.inline_keyboard[0][0].text == BTN_SHOW_STANDS
    assert inline_markup.inline_keyboard[0][0].callback_data == CB_STANDS

    reply_markup = map_sec.get_reply_markup(inline=False)
    assert reply_markup is not None
    assert hasattr(reply_markup, "keyboard")


@pytest.mark.asyncio
async def test_map_section_callbacks_and_stand_participants(tmp_path):
    part_file = tmp_path / "participants.json"
    part_file.write_text(
        json.dumps({
            "participants": [
                {"name": "Издатель 1", "stand": "1"},
                {"name": "Издатель 2", "stand": "1"},
                {"name": "Издатель 3", "stand": "2"},
            ]
        }),
        encoding="utf-8",
    )
    from bot.participants.service import ParticipantsService

    svc = ParticipantsService(file_path=str(part_file))
    map_sec = Map(participants_service=svc)

    assert map_sec.matches_callback(CB_MAP)
    assert map_sec.matches_callback(CB_STANDS)
    assert map_sec.matches_callback("stand:0")
    assert map_sec.matches_callback("stand:1")

    # When CB_STANDS is tapped -> shows grid of stands
    query_stands = AsyncMock()
    query_stands.data = CB_STANDS
    query_stands.edit_message_reply_markup = AsyncMock()
    await map_sec.handle_callback_query(query_stands)
    query_stands.edit_message_reply_markup.assert_awaited_once()
    stands_markup = query_stands.edit_message_reply_markup.call_args.kwargs["reply_markup"]
    assert len(stands_markup.inline_keyboard) == 1
    assert stands_markup.inline_keyboard[0][0].text == "1"
    assert stands_markup.inline_keyboard[0][1].text == "2"

    # When stand:0 is selected (stand "1", has 2 participants)
    query = AsyncMock()
    query.data = "stand:0"
    await map_sec.handle_callback_query(query)

    query.edit_message_text.assert_awaited_once()
    kwargs = query.edit_message_text.call_args.kwargs
    assert "Стенд 1" in kwargs["text"]
    assert "Выберите участника" in kwargs["text"]
    markup = kwargs["reply_markup"]
    assert len(markup.inline_keyboard) == 3  # 2 participant buttons + 1 back to map
    assert "Издатель 1" in markup.inline_keyboard[0][0].text
    assert "Издатель 2" in markup.inline_keyboard[1][0].text
    assert markup.inline_keyboard[0][0].callback_data == "part_item:0:s:0"
    assert markup.inline_keyboard[1][0].callback_data == "part_item:1:s:0"
    assert markup.inline_keyboard[2][0].callback_data == CB_MAP

    # When participant 0 from stand is clicked -> participant details with back button to stand:0
    part_sec = Participants(service=svc)
    query_part = AsyncMock()
    query_part.data = markup.inline_keyboard[0][0].callback_data
    await part_sec.handle_callback_query(query_part)
    query_part.edit_message_text.assert_awaited_once()
    part_kwargs = query_part.edit_message_text.call_args.kwargs
    assert "Издатель 1" in part_kwargs["text"]
    part_details_markup = part_kwargs["reply_markup"]
    assert len(part_details_markup.inline_keyboard) == 1
    back_to_stand_btn = part_details_markup.inline_keyboard[0][0]
    assert back_to_stand_btn.callback_data == "stand:0"

    # When back to stand is clicked -> returns to stand:0 participant list
    query_back = AsyncMock()
    query_back.data = back_to_stand_btn.callback_data
    await map_sec.handle_callback_query(query_back)
    query_back.edit_message_text.assert_awaited_once()
    assert "Стенд 1" in query_back.edit_message_text.call_args.kwargs["text"]


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
async def test_children_activity_section(mock_message):
    ca = ChildrenActivity()
    assert ca.name == "children"
    assert ca.matches_command("children")
    assert ca.matches_command("children_activity")
    assert ca.matches_command("kids")
    assert ca.matches_callback(CB_CHILDREN_ACTIVITY)
    assert ca.matches_text(BTN_CHILDREN_ACTIVITY)
    assert ca.matches_text("детская программа")
    assert ca.matches_text("дети")
    assert ca.get_text_content() == CHILDREN_ACTIVITY_MESSAGE

    await ca.send_response(mock_message)
    mock_message.reply_text.assert_awaited_once()
    kwargs = mock_message.reply_text.call_args.kwargs
    assert kwargs["text"] == CHILDREN_ACTIVITY_MESSAGE
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
    assert isinstance(registry.find_by_command("children"), ChildrenActivity)
    assert isinstance(registry.find_by_command("kids"), ChildrenActivity)
    assert isinstance(registry.find_by_command("recs"), Recommendations)
    assert isinstance(registry.find_by_command("participants"), Participants)
    assert isinstance(registry.find_by_command("stands"), Participants)
    assert isinstance(registry.find_by_command("help"), Help)
    assert registry.find_by_command("nonexistent") is None

    # Callbacks
    assert isinstance(registry.find_by_callback(CB_MAP), Map)
    assert isinstance(registry.find_by_callback(CB_TIMETABLE), Timetable)
    assert isinstance(registry.find_by_callback(CB_CHILDREN_ACTIVITY), ChildrenActivity)
    assert isinstance(registry.find_by_callback(CB_RECOMMENDATIONS), Recommendations)
    assert isinstance(registry.find_by_callback(CB_PARTICIPANTS), Participants)
    assert isinstance(registry.find_by_callback(CB_HELP), Help)
    assert registry.find_by_callback("unknown_cb") is None

    # Text / Aliases / Buttons
    assert isinstance(registry.find_by_text(BTN_MAP), Map)
    assert isinstance(registry.find_by_text("карта"), Map)
    assert isinstance(registry.find_by_text(BTN_TIMETABLE), Timetable)
    assert isinstance(registry.find_by_text("программа"), Timetable)
    assert isinstance(registry.find_by_text(BTN_CHILDREN_ACTIVITY), ChildrenActivity)
    assert isinstance(registry.find_by_text("детская программа"), ChildrenActivity)
    assert isinstance(registry.find_by_text("дети"), ChildrenActivity)
    assert isinstance(registry.find_by_text(BTN_RECOMMENDATIONS), Recommendations)
    assert isinstance(registry.find_by_text("рекомендации"), Recommendations)
    assert isinstance(registry.find_by_text(BTN_PARTICIPANTS), Participants)
    assert isinstance(registry.find_by_text("участники"), Participants)
    assert isinstance(registry.find_by_text("стенды"), Participants)
    assert isinstance(registry.find_by_text(BTN_HELP), Help)
    assert isinstance(registry.find_by_text("помощь"), Help)
    assert registry.find_by_text("unrecognized input") is None


def test_one_class_per_module_imports():
    assert BaseSection is DirectBaseSection
    assert Start is DirectStart
    assert Help is DirectHelp
    assert Map is DirectMap
    assert Timetable is DirectTimetable
    assert ChildrenActivity is DirectChildrenActivity
    assert Recommendations is DirectRecommendations
    assert Participants is DirectParticipants
    assert SectionRegistry is DirectSectionRegistry
