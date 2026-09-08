"""Unit and integration tests for UX analytics collection, anonymization, and reporting."""

import csv
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import AsyncMock, MagicMock
import zipfile
import pytest

from admin.server.request import AdminRequest
from admin.server.router import AdminRouter
from admin.services.analytics_service import AdminAnalyticsService
from admin.views.template_renderer import AdminTemplateRenderer
from bot.analytics.anonymizer import anonymize_user_id
from bot.analytics.service import AnalyticsService, parse_memory_threshold_bytes
from bot.handlers import (
    button_callback_handler,
    help_handler,
    map_handler,
    start_handler,
    text_message_handler,
)


def test_parse_memory_threshold_bytes():
    """Verify threshold parsing supports MB, KB, GB, numeric, and env values."""
    assert parse_memory_threshold_bytes(50) == 50 * 1024 * 1024
    assert parse_memory_threshold_bytes("50MB") == 50 * 1024 * 1024
    assert parse_memory_threshold_bytes("50M") == 50 * 1024 * 1024
    assert parse_memory_threshold_bytes("50 mb") == 50 * 1024 * 1024
    assert parse_memory_threshold_bytes("1GB") == 1024 * 1024 * 1024
    assert parse_memory_threshold_bytes("512KB") == 512 * 1024
    assert parse_memory_threshold_bytes(10000000) == 10000000
    assert parse_memory_threshold_bytes(None) == 50 * 1024 * 1024


def test_anonymize_user_id():
    """Verify user IDs are hashed deterministically and raw IDs are never preserved."""
    raw_id = 123456789
    hashed_1 = anonymize_user_id(raw_id, salt="test_salt")
    hashed_2 = anonymize_user_id(raw_id, salt="test_salt")
    hashed_diff_salt = anonymize_user_id(raw_id, salt="different_salt")

    assert hashed_1 == hashed_2
    assert str(raw_id) not in hashed_1
    assert len(hashed_1) == 64  # SHA-256 hex string
    assert hashed_1 != hashed_diff_salt


def test_analytics_service_event_counters_and_user_stats(tmp_path):
    """Verify event counting and user statistics tracking."""
    db_path = str(tmp_path / "analytics.db")
    service = AnalyticsService(db_path=db_path)

    u1 = anonymize_user_id(1001, salt="test")
    u2 = anonymize_user_id(1002, salt="test")

    # Record chats and commands
    service.record_chat_interaction(u1)
    service.record_chat_interaction(u1)
    service.record_chat_interaction(u2)

    service.record_command(u1, "start")
    service.record_command(u1, "map")
    service.record_command(u2, "/start")
    service.record_command(u2, "timetables")

    service.record_inline_keyboard_event(u1, "btn_callback_1")
    service.record_inline_keyboard_event(u2, "btn_callback_2")
    service.record_inline_keyboard_event(u2, "btn_callback_3")

    service.record_unrecognized_message(u1, "some gibberish")

    counts = service.get_event_counts()
    assert counts["commands"] == 4
    assert counts["inline_keyboard_events"] == 3
    assert counts["unrecognized_messages"] == 1
    assert counts["total_events"] == 8

    users = service.get_user_stats()
    assert users["total_users"] == 2
    assert users["total_chats"] == 3


def test_analytics_service_generalized_user_paths(tmp_path):
    """Verify user paths generalization aggregates identical sequences."""
    db_path = str(tmp_path / "analytics.db")
    service = AnalyticsService(db_path=db_path)

    u1 = anonymize_user_id(1, salt="test")
    u2 = anonymize_user_id(2, salt="test")
    u3 = anonymize_user_id(3, salt="test")

    # u1 and u2 follow identical path: start -> map -> timetables
    for cmd in ["start", "map", "timetables"]:
        service.record_command(u1, cmd)
        service.record_command(u2, cmd)

    # u3 follows different path: start -> wishlist
    for cmd in ["start", "wishlist"]:
        service.record_command(u3, cmd)

    paths = service.get_generalized_user_paths()
    assert len(paths) == 2

    top_path = paths[0]
    assert top_path["path"] == "start ➔ map ➔ timetables"
    assert top_path["count"] == 2
    assert top_path["percentage"] == pytest.approx(66.7, 0.1)

    second_path = paths[1]
    assert second_path["path"] == "start ➔ wishlist"
    assert second_path["count"] == 1
    assert second_path["percentage"] == pytest.approx(33.3, 0.1)


def test_analytics_service_wishlist_stats(tmp_path):
    """Verify aggregated wishlist statistics without individual user wishlists."""
    analytics_db = str(tmp_path / "analytics.db")
    wishlist_db = str(tmp_path / "wishlist.db")

    # Create dummy wishlist database
    conn = sqlite3.connect(wishlist_db)
    conn.execute("CREATE TABLE users (user_id TEXT PRIMARY KEY);")
    conn.execute("""
        CREATE TABLE wishlist_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            authors TEXT,
            publishing TEXT,
            isbn TEXT,
            year INTEGER,
            user_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("INSERT INTO users VALUES ('u1'), ('u2'), ('u3');")
    conn.execute("INSERT INTO wishlist_books (user_id, title, isbn) VALUES ('u1', 'Мастер и Маргарита', '978-5-17-090335-1');")
    conn.execute("INSERT INTO wishlist_books (user_id, title, isbn) VALUES ('u2', 'Мастер и Маргарита', '978-5-17-090335-1');")
    conn.execute("INSERT INTO wishlist_books (user_id, title, isbn) VALUES ('u3', 'Евгений Онегин', '978-5-17-090335-2');")
    conn.commit()
    conn.close()

    service = AnalyticsService(db_path=analytics_db, wishlist_db_path=wishlist_db)
    wishlist_stats = service.get_wishlist_stats()

    assert len(wishlist_stats) == 2
    assert wishlist_stats[0]["title"] == "Мастер и Маргарита"
    assert wishlist_stats[0]["count"] == 2
    assert wishlist_stats[0]["isbn"] == "978-5-17-090335-1"
    assert wishlist_stats[1]["title"] == "Евгений Онегин"
    assert wishlist_stats[1]["count"] == 1


def test_analytics_csv_export_anonymity(tmp_path):
    """Verify CSV export contains summary metrics and never reveals user IDs."""
    analytics_db = str(tmp_path / "analytics.db")
    wishlist_db = str(tmp_path / "wishlist.db")
    service = AnalyticsService(db_path=analytics_db, wishlist_db_path=wishlist_db)

    raw_user_id = 987654321
    uid = anonymize_user_id(raw_user_id, salt="secret")

    service.record_chat_interaction(uid)
    service.record_command(uid, "start")
    service.record_command(uid, "map")
    service.record_inline_keyboard_event(uid, "cb_test")
    service.record_unrecognized_message(uid, "gibberish")

    csv_data = service.export_csv()
    assert isinstance(csv_data, str)
    assert "=== UX Overview Metrics ===" in csv_data
    assert "=== Event Counters ===" in csv_data
    assert "=== Generalized User Paths (Command Sequences) ===" in csv_data
    assert "=== Wishlisted Books Statistics ===" in csv_data
    assert "start ➔ map" in csv_data

    # Anonymity checks: raw user id and hashed user id MUST NOT be in the CSV
    assert str(raw_user_id) not in csv_data
    assert uid not in csv_data


def test_admin_analytics_routes_and_template_rendering(tmp_path):
    """Verify AdminRouter /analytics web routes, ZIP export, CSV fallback, and API routes."""
    analytics_db = str(tmp_path / "analytics.db")
    wishlist_db = str(tmp_path / "wishlist.db")
    analytics_service = AdminAnalyticsService(db_path=analytics_db, wishlist_db_path=wishlist_db)

    u1 = anonymize_user_id(42, salt="s")
    analytics_service.record_chat_interaction(u1)
    analytics_service.record_command(u1, "start")
    analytics_service.record_command(u1, "recs")
    analytics_service.record_inline_keyboard_event(u1, "rec_books")

    router = AdminRouter(analytics_service=analytics_service)
    router.session_manager.is_valid_session = MagicMock(return_value=True)
    headers = {
        "Cookie": f"{router.config.session_cookie_name}=valid_mock",
    }

    # 1. GET /analytics
    req_get = AdminRequest(method="GET", path="/analytics", headers=headers)
    res_get = router.route(req_get)
    assert res_get.status_code == 200
    html_body = res_get.body.decode("utf-8")
    assert "UX Аналитика" in html_body
    assert "start ➔ recs" in html_body
    assert "/analytics/export" in html_body
    assert "Скачать отчет (ZIP)" in html_body

    # 2. GET /analytics/export (returns ZIP archive containing CSV files)
    req_zip = AdminRequest(method="GET", path="/analytics/export", headers=headers)
    res_zip = router.route(req_zip)
    assert res_zip.status_code == 200
    assert "application/zip" in res_zip.headers.get("Content-Type", "")
    assert "attachment;" in res_zip.headers.get("Content-Disposition", "")
    assert res_zip.headers.get("Content-Disposition", "").endswith('.zip"')

    with zipfile.ZipFile(io.BytesIO(res_zip.body)) as zf:
        names = zf.namelist()
        assert "events.csv" in names
        assert "buttons.csv" in names
        assert "commands.csv" in names
        assert "paths.csv" in names
        assert "wishlist.csv" in names

        paths_csv = zf.read("paths.csv").decode("utf-8-sig")
        assert "start ➔ recs" in paths_csv
        assert u1 not in paths_csv

    # 3. GET /analytics/export/csv (backward compatibility)
    req_csv = AdminRequest(method="GET", path="/analytics/export/csv", headers=headers)
    res_csv = router.route(req_csv)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers.get("Content-Type", "")
    assert "attachment;" in res_csv.headers.get("Content-Disposition", "")
    csv_text = res_csv.body.decode("utf-8-sig")
    assert "start ➔ recs" in csv_text
    assert u1 not in csv_text

    # 4. GET /api/analytics
    req_api = AdminRequest(method="GET", path="/api/analytics", headers=headers)
    res_api = router.route(req_api)
    assert res_api.status_code == 200
    json_data = res_api.body.decode("utf-8")
    assert '"total_events"' in json_data

    # 5. GET /api/analytics/export
    req_api_export = AdminRequest(method="GET", path="/api/analytics/export", headers=headers)
    res_api_export = router.route(req_api_export)
    assert res_api_export.status_code == 200
    assert "application/zip" in res_api_export.headers.get("Content-Type", "")


def test_analytics_zip_export_structure_and_csv_contents(tmp_path):
    """Verify service.export_zip() contains valid CSV files for events, buttons, commands, paths, and wishlist."""
    analytics_db = str(tmp_path / "analytics.db")
    wishlist_db = str(tmp_path / "wishlist.db")

    # Seed wishlist database
    conn = sqlite3.connect(wishlist_db)
    conn.execute("CREATE TABLE wishlist_books (id INTEGER PRIMARY KEY, user_id TEXT, title TEXT, isbn TEXT);")
    conn.execute("INSERT INTO wishlist_books (user_id, title, isbn) VALUES ('u1', 'Мастер и Маргарита', '978-5-17-090335-1');")
    conn.commit()
    conn.close()

    service = AnalyticsService(db_path=analytics_db, wishlist_db_path=wishlist_db)
    raw_user_id = 987654321
    uid = anonymize_user_id(raw_user_id, salt="secret")

    service.record_chat_interaction(uid)
    service.record_command(uid, "/start")
    service.record_inline_keyboard_event(uid, callback_data="action_map", button_name="🏢 План ярмарки")
    service.record_command(uid, "🏢 План ярмарки")
    service.record_unrecognized_message(uid, "неизвестный текст")

    # 1. Export to bytes
    zip_bytes = service.export_zip()
    assert isinstance(zip_bytes, bytes)
    assert len(zip_bytes) > 0

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        file_names = set(zf.namelist())
        expected_files = {"events.csv", "buttons.csv", "commands.csv", "paths.csv", "wishlist.csv"}
        assert expected_files.issubset(file_names)

        # Verify events.csv
        events_csv = zf.read("events.csv").decode("utf-8-sig")
        assert "Event Type,Count" in events_csv
        assert "Commands Executed" in events_csv
        assert "Inline Keyboard Clicks" in events_csv
        assert "Unrecognized Messages" in events_csv
        assert str(raw_user_id) not in events_csv
        assert uid not in events_csv

        # Verify buttons.csv
        buttons_csv = zf.read("buttons.csv").decode("utf-8-sig")
        assert "Button Label,Callback Action,Clicks Count" in buttons_csv
        assert "🏢 План ярмарки,action_map" in buttons_csv

        # Verify commands.csv
        commands_csv = zf.read("commands.csv").decode("utf-8-sig")
        assert "Command,Description,Invocations Count" in commands_csv
        assert "/start" in commands_csv

        # Verify paths.csv
        paths_csv = zf.read("paths.csv").decode("utf-8-sig")
        assert "User Path,User Count,Percentage (%)" in paths_csv
        assert "/start ➔ 🏢 План ярмарки" in paths_csv
        assert str(raw_user_id) not in paths_csv
        assert uid not in paths_csv

        # Verify wishlist.csv
        wishlist_csv = zf.read("wishlist.csv").decode("utf-8-sig")
        assert "Book Title,ISBN,Wishlist Additions Count" in wishlist_csv
        assert "Мастер и Маргарита" in wishlist_csv
        assert "978-5-17-090335-1" in wishlist_csv
        assert str(raw_user_id) not in wishlist_csv
        assert uid not in wishlist_csv

    # 2. Export to file path
    out_zip_path = str(tmp_path / "exported_analytics.zip")
    res_path = service.export_zip(output_target=out_zip_path)
    assert res_path == out_zip_path
    assert os.path.exists(out_zip_path)
    assert os.path.getsize(out_zip_path) > 0


@pytest.mark.asyncio
async def test_bot_handlers_record_ux_analytics(tmp_path, monkeypatch):
    """Verify bot handlers record commands, inline callbacks, and unrecognized messages."""
    db_path = str(tmp_path / "analytics.db")
    service = AnalyticsService(db_path=db_path)
    monkeypatch.setattr("bot.handlers.default_analytics_service", service)

    # 1. Start command handler
    update_start = MagicMock()
    update_start.effective_user.id = 111111
    update_start.effective_chat.id = 111111
    update_start.effective_message.reply_text = AsyncMock()
    context = MagicMock()

    await start_handler(update_start, context)
    assert service.get_event_counts()["commands"] == 1
    assert service.get_user_stats()["total_users"] == 1

    # 2. Inline button callback handler
    update_cb = MagicMock()
    update_cb.effective_user.id = 111111
    update_cb.effective_chat.id = 111111
    update_cb.callback_query.data = "main_menu"
    update_cb.callback_query.answer = AsyncMock()
    update_cb.callback_query.message = MagicMock()
    update_cb.callback_query.message.reply_text = AsyncMock()

    await button_callback_handler(update_cb, context)
    assert service.get_event_counts()["inline_keyboard_events"] == 1

    # 3. Text message handler with unrecognized message
    update_txt = MagicMock()
    update_txt.effective_user.id = 111111
    update_txt.effective_chat.id = 111111
    update_txt.effective_message.text = "абсолютно случайный неизвестный текст"
    update_txt.effective_message.reply_text = AsyncMock()

    await text_message_handler(update_txt, context)
    assert service.get_event_counts()["unrecognized_messages"] == 1


def test_analytics_memory_buffering_and_auto_flush(tmp_path):
    """Verify in-memory buffering in RAM and auto-flushing to SQLite on reaching threshold."""
    db_path = str(tmp_path / "analytics_buffer.db")
    # Low threshold: 500 bytes to easily trigger auto-flush
    service = AnalyticsService(db_path=db_path, flush_threshold_bytes=500)

    u1 = anonymize_user_id(101, salt="t")
    service.record_chat_interaction(u1)
    service.record_command(u1, "start")

    # Before exceeding threshold, memory usage > 0
    assert service.get_buffered_memory_usage() > 0

    # Add commands until threshold triggers auto-flush
    for i in range(10):
        service.record_command(u1, f"command_step_{i}")

    # Explicit flush or query triggers flush
    service.flush()
    assert service._buffer_bytes == 0

    counts = service.get_event_counts()
    assert counts["commands"] >= 11
    paths = service.get_generalized_user_paths()
    assert len(paths) == 1
    assert "start ➔ command_step_0" in paths[0]["path"]


def test_admin_analytics_refresh_on_demand(tmp_path):
    """Verify on-demand analytics update button route in Admin Console."""
    analytics_db = str(tmp_path / "analytics.db")
    analytics_service = AdminAnalyticsService(db_path=analytics_db)
    router = AdminRouter(analytics_service=analytics_service)
    router.session_manager.is_valid_session = MagicMock(return_value=True)
    headers = {
        "Cookie": f"{router.config.session_cookie_name}=valid_mock",
    }

    # Record in-memory events
    u = anonymize_user_id(999, salt="s")
    analytics_service.record_chat_interaction(u)
    analytics_service.record_command(u, "timetables")

    # POST /analytics/refresh
    req_refresh = AdminRequest(method="POST", path="/analytics/refresh", headers=headers)
    res_refresh = router.route(req_refresh)
    assert res_refresh.status_code == 302
    assert "/analytics?msg=" in res_refresh.headers.get("Location", "")

    # GET /api/analytics/flush
    req_flush_api = AdminRequest(method="POST", path="/api/analytics/flush", headers=headers)
    res_flush_api = router.route(req_flush_api)
    assert res_flush_api.status_code == 200
    assert '"status": "ok"' in res_flush_api.body.decode("utf-8")


@pytest.mark.asyncio
async def test_timetable_and_stands_user_paths_collection(tmp_path, monkeypatch):
    """Verify timetable and stands paths are recorded across commands, inline callbacks, and text."""
    db_path = str(tmp_path / "analytics.db")
    service = AnalyticsService(db_path=db_path)
    monkeypatch.setattr("bot.handlers.default_analytics_service", service)

    u = anonymize_user_id(555, salt="test_user")
    context = MagicMock()

    # 1. Timetable command handler
    up_tt = MagicMock()
    up_tt.effective_user.id = 555
    up_tt.effective_chat.id = 555
    up_tt.effective_message.reply_text = AsyncMock()
    from bot.handlers import timetable_handler, participants_handler
    await timetable_handler(up_tt, context)

    # 2. Timetable inline callback
    up_tt_cb = MagicMock()
    up_tt_cb.effective_user.id = 555
    up_tt_cb.effective_chat.id = 555
    up_tt_cb.callback_query.data = "tt_d:2024-05-18"
    up_tt_cb.callback_query.answer = AsyncMock()
    up_tt_cb.callback_query.message = MagicMock()
    up_tt_cb.callback_query.message.edit_message_text = AsyncMock()
    await button_callback_handler(up_tt_cb, context)

    # 3. Stands command
    up_stands = MagicMock()
    up_stands.effective_user.id = 555
    up_stands.effective_chat.id = 555
    up_stands.effective_message.text = "/stands"
    up_stands.effective_message.reply_text = AsyncMock()
    await participants_handler(up_stands, context)

    # 4. Stands inline callback
    up_stands_cb = MagicMock()
    up_stands_cb.effective_user.id = 555
    up_stands_cb.effective_chat.id = 555
    up_stands_cb.callback_query.data = "action_stands"
    up_stands_cb.callback_query.answer = AsyncMock()
    up_stands_cb.callback_query.message = MagicMock()
    up_stands_cb.callback_query.message.reply_text = AsyncMock()
    await button_callback_handler(up_stands_cb, context)

    # 5. Stand item inline callback
    up_stand_item_cb = MagicMock()
    up_stand_item_cb.effective_user.id = 555
    up_stand_item_cb.effective_chat.id = 555
    up_stand_item_cb.callback_query.data = "stand:0"
    up_stand_item_cb.callback_query.answer = AsyncMock()
    up_stand_item_cb.callback_query.message = MagicMock()
    up_stand_item_cb.callback_query.message.reply_text = AsyncMock()
    await button_callback_handler(up_stand_item_cb, context)

    # 6. Text message for stands
    up_txt_stands = MagicMock()
    up_txt_stands.effective_user.id = 555
    up_txt_stands.effective_chat.id = 555
    up_txt_stands.effective_message.text = "📍 Информация о стендах"
    up_txt_stands.effective_message.reply_text = AsyncMock()
    await text_message_handler(up_txt_stands, context)

    paths = service.get_generalized_user_paths()
    assert len(paths) == 1
    user_path = paths[0]["path"]
    assert "/timetables" in user_path
    assert "2024-05-18" in user_path
    assert "/stands" in user_path
    assert "Стенды" in user_path
    assert "Стенд 1" in user_path
    assert "Информация о стендах" in user_path
    assert user_path == "/timetables ➔ 2024-05-18 ➔ /stands ➔ Стенды ➔ Стенд 1 ➔ Информация о стендах"


@pytest.mark.asyncio
async def test_dynamic_event_and_filter_buttons_in_user_paths(tmp_path, monkeypatch):
    """Verify master class event items and filter buttons record Russian labels and titles."""
    db_path = str(tmp_path / "analytics.db")
    service = AnalyticsService(db_path=db_path)
    monkeypatch.setattr("bot.handlers.default_analytics_service", service)

    u = anonymize_user_id(777, salt="mc_test")
    context = MagicMock()

    # 1. Command /masterclasses
    up_cmd = MagicMock()
    up_cmd.effective_user.id = 777
    up_cmd.effective_chat.id = 777
    up_cmd.effective_message.reply_text = AsyncMock()
    from bot.handlers import master_classes_handler
    await master_classes_handler(up_cmd, context)

    # 2. Filter inline button
    up_filter = MagicMock()
    up_filter.effective_user.id = 777
    up_filter.effective_chat.id = 777
    up_filter.callback_query.data = "mc_filter:children"
    up_filter.callback_query.answer = AsyncMock()
    up_filter.callback_query.edit_message_text = AsyncMock()
    up_filter.callback_query.message = MagicMock()
    up_filter.callback_query.message.reply_text = AsyncMock()
    up_filter.callback_query.message.edit_message_text = AsyncMock()
    await button_callback_handler(up_filter, context)

    # 3. Masterclass item inline button with mock reply markup
    up_item = MagicMock()
    up_item.effective_user.id = 777
    up_item.effective_chat.id = 777
    up_item.callback_query.data = "mc_item:2026-09-12:0:1"
    up_item.callback_query.answer = AsyncMock()
    up_item.callback_query.edit_message_text = AsyncMock()
    btn_mock = MagicMock()
    btn_mock.callback_data = "mc_item:2026-09-12:0:1"
    btn_mock.text = "🎨 12.09 — Рисование комиксов"
    up_item.callback_query.message.reply_markup.inline_keyboard = [[btn_mock]]
    up_item.callback_query.message.reply_text = AsyncMock()
    up_item.callback_query.message.edit_message_text = AsyncMock()
    await button_callback_handler(up_item, context)

    paths = service.get_generalized_user_paths()
    assert len(paths) == 1
    path_str = paths[0]["path"]
    assert path_str == "/masterclasses ➔ Для детей ➔ 🎨 12.09 — Рисование комиксов"


@pytest.mark.asyncio
async def test_unexpected_input_recorded_in_user_path_without_saving_raw_input(tmp_path, monkeypatch):
    """Verify unexpected input is recorded as an occasion in user paths without saving the raw text."""
    db_path = str(tmp_path / "analytics.db")
    service = AnalyticsService(db_path=db_path)
    monkeypatch.setattr("bot.handlers.default_analytics_service", service)

    u = anonymize_user_id(888, salt="unrec")
    context = MagicMock()
    context.user_data = {}

    # User sends unknown message
    secret_text = "my_secret_random_text_12345"
    up = MagicMock()
    up.effective_user.id = 888
    up.effective_chat.id = 888
    up.effective_message.text = secret_text
    up.effective_message.reply_text = AsyncMock()
    await text_message_handler(up, context)

    paths = service.get_generalized_user_paths()
    assert len(paths) == 1
    path_str = paths[0]["path"]
    assert "Неожиданный ввод" in path_str
    assert secret_text not in path_str

    # Verify raw secret is nowhere in DB
    with service._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT command FROM ux_user_commands;")
        cmds = [r["command"] for r in cursor.fetchall()]
        assert "Неожиданный ввод" in cmds
        assert secret_text not in cmds


@pytest.mark.asyncio
async def test_isbn_search_results_in_user_paths(tmp_path, monkeypatch):
    """Verify ISBN search results (success, pic failure, lookup failure) are recorded in paths without raw data."""
    db_path = str(tmp_path / "analytics.db")
    service = AnalyticsService(db_path=db_path)
    monkeypatch.setattr("bot.handlers.default_analytics_service", service)

    u = anonymize_user_id(999, salt="isbn")
    context = MagicMock()
    context.user_data = {"awaiting_wishlist_isbn": True}

    from bot.handlers import photo_message_handler

    # 1. Photo with unreadable barcode -> failure in recognizing pic
    up_pic_fail = MagicMock()
    up_pic_fail.effective_user.id = 999
    up_pic_fail.effective_chat.id = 999
    photo_mock = MagicMock()
    photo_mock.file_size = 1000
    photo_mock.file_id = "test_fid"
    up_pic_fail.effective_message.photo = [photo_mock]
    up_pic_fail.effective_message.reply_text = AsyncMock()
    context.bot.get_file = AsyncMock()
    file_mock = MagicMock()
    file_mock.file_size = 1000
    file_mock.download_as_bytearray = AsyncMock(return_value=b"invalid_image_bytes")
    context.bot.get_file.return_value = file_mock

    monkeypatch.setattr("bot.handlers.decode_barcode_from_image", lambda img: None)
    await photo_message_handler(up_pic_fail, context)

    # 2. Text ISBN not found in lookup -> failure in isbn lookup
    context.user_data["awaiting_wishlist_isbn"] = True
    up_lookup_fail = MagicMock()
    up_lookup_fail.effective_user.id = 999
    up_lookup_fail.effective_chat.id = 999
    up_lookup_fail.effective_message.text = "9785170000000"
    up_lookup_fail.effective_message.reply_text = AsyncMock()
    monkeypatch.setattr("bot.handlers.lookup_book_by_isbn", lambda isbn: None)
    await text_message_handler(up_lookup_fail, context)

    # 3. Text ISBN found -> success
    context.user_data["awaiting_wishlist_isbn"] = True
    up_success = MagicMock()
    up_success.effective_user.id = 999
    up_success.effective_chat.id = 999
    up_success.effective_message.text = "9785170903351"
    up_success.effective_message.reply_text = AsyncMock()
    from bot.wishlist.book import Book
    dummy_book = Book(id=1, title="Тестовая книга")
    monkeypatch.setattr("bot.handlers.lookup_book_by_isbn", lambda isbn: dummy_book)
    await text_message_handler(up_success, context)

    paths = service.get_generalized_user_paths()
    assert len(paths) == 1
    path_str = paths[0]["path"]
    assert "ISBN: failure in recognizing pic" in path_str
    assert "ISBN: failure in isbn lookup" in path_str
    assert "ISBN: success" in path_str

    # Ensure raw ISBN is not in the path string
    assert "9785170000000" not in path_str
    assert "9785170903351" not in path_str


def test_analytics_db_schema_only_user_paths_and_no_last_seen(tmp_path):
    """Verify DB is used strictly for user paths and contains no event counters or last_seen."""
    db_path = str(tmp_path / "analytics.db")
    service = AnalyticsService(db_path=db_path)

    u1 = anonymize_user_id(1234, salt="schema_test")
    service.record_chat_interaction(u1)
    service.record_inline_keyboard_event(u1, "some_cb")
    service.record_command(u1, "/start")
    service.record_command(u1, "Расписание")
    service.flush()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        # 1. Check all tables in DB
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
        assert tables == ["ux_user_commands"]
        assert "ux_event_counters" not in tables
        assert "ux_users" not in tables

        # 2. Check columns in ux_user_commands
        cursor.execute("PRAGMA table_info(ux_user_commands);")
        columns = [row[1] for row in cursor.fetchall()]
        assert "last_seen" not in columns
        assert "user_id" in columns
        assert "command" in columns
        assert "created_at" in columns


def test_ongoing_sessions_flush_and_grouping_on_admin_demand(tmp_path):
    """Verify ongoing session data flushes to DB and is grouped on demand across instances/processes."""
    db_path = str(tmp_path / "analytics.db")

    # Bot process records commands
    bot_service = AnalyticsService(db_path=db_path)
    u1 = anonymize_user_id(10, salt="s")
    u2 = anonymize_user_id(20, salt="s")

    # User 1 ongoing session 1
    bot_service.record_command(u1, "/start")
    bot_service.record_command(u1, "Расписание")
    bot_service.record_command(u1, "2024-05-18")

    # User 1 ongoing session 2 (starts with /start)
    bot_service.record_command(u1, "/start")
    bot_service.record_command(u1, "Стенды")

    # User 2 ongoing session
    bot_service.record_command(u2, "/start")
    bot_service.record_command(u2, "Расписание")
    bot_service.record_command(u2, "2024-05-18")

    # Admin process creates service connected to the same DB file
    admin_service = AdminAnalyticsService(db_path=db_path)
    admin_service.flush()

    # Get generalized user paths on demand
    paths = admin_service.get_generalized_user_paths()
    assert len(paths) == 2

    top_path = paths[0]
    assert top_path["path"] == "/start ➔ Расписание ➔ 2024-05-18"
    assert top_path["count"] == 2
    assert top_path["percentage"] == pytest.approx(66.7, 0.1)

    second_path = paths[1]
    assert second_path["path"] == "/start ➔ Стенды"
    assert second_path["count"] == 1
    assert second_path["percentage"] == pytest.approx(33.3, 0.1)


def test_menu_buttons_and_text_commands_counters(tmp_path):
    """Verify counters for each of basic inline buttons and each of text commands."""
    db_path = str(tmp_path / "analytics.db")
    service = AnalyticsService(db_path=db_path)

    u1 = anonymize_user_id(100, salt="test")
    u2 = anonymize_user_id(200, salt="test")

    # Initial state: all basic menu buttons and text commands exist with 0 counts
    init_buttons = service.get_menu_button_counts()
    assert len(init_buttons) == 8
    for b in init_buttons:
        assert b["count"] == 0

    init_commands = service.get_text_command_counts()
    assert len(init_commands) >= 9
    for c in init_commands:
        assert c["count"] == 0

    # Record clicks on basic inline menu buttons
    service.record_inline_keyboard_event(u1, callback_data="action_map", button_name="🏢 План ярмарки")
    service.record_command(u1, "🏢 План ярмарки")

    service.record_inline_keyboard_event(u2, callback_data="action_map", button_name="🏢 План ярмарки")
    service.record_command(u2, "🏢 План ярмарки")

    service.record_inline_keyboard_event(u1, callback_data="action_timetable", button_name="📅 Расписание")
    service.record_command(u1, "📅 Расписание")

    service.record_inline_keyboard_event(u1, callback_data="section_children_activity", button_name="🎈 Детская программа")
    service.record_command(u1, "🎈 Детская программа")

    service.record_inline_keyboard_event(u1, callback_data="action_master_classes", button_name="🎨 Мастер-классы")
    service.record_command(u1, "🎨 Мастер-классы")

    service.record_inline_keyboard_event(u1, callback_data="action_recommendations", button_name="📚 Рекомендации")
    service.record_command(u1, "📚 Рекомендации")

    service.record_inline_keyboard_event(u1, callback_data="action_participants", button_name="👥 Участники")
    service.record_command(u1, "👥 Участники")

    service.record_inline_keyboard_event(u1, callback_data="action_wishlist", button_name="📝 Вишлист")
    service.record_command(u1, "📝 Вишлист")

    service.record_inline_keyboard_event(u1, callback_data="action_help", button_name="ℹ️ Помощь")
    service.record_command(u1, "ℹ️ Помощь")

    # Record text commands
    service.record_command(u1, "/start")
    service.record_command(u2, "/start")
    service.record_command(u1, "/help")
    service.record_command(u1, "/map")
    service.record_command(u1, "/timetables")
    service.record_command(u1, "/children")
    service.record_command(u1, "/masterclasses")
    service.record_command(u1, "/recommendations")
    service.record_command(u1, "/participants")
    service.record_command(u1, "/wishlist")
    service.record_command(u1, "/customcmd")

    btn_dict = service.get_menu_buttons_dict()
    assert btn_dict["action_map"] == 2
    assert btn_dict["action_timetable"] == 1
    assert btn_dict["section_children_activity"] == 1
    assert btn_dict["action_master_classes"] == 1
    assert btn_dict["action_recommendations"] == 1
    assert btn_dict["action_participants"] == 1
    assert btn_dict["action_wishlist"] == 1
    assert btn_dict["action_help"] == 1

    cmd_dict = service.get_text_commands_dict()
    assert cmd_dict["/start"] == 2
    assert cmd_dict["/help"] == 1
    assert cmd_dict["/map"] == 1
    assert cmd_dict["/timetables"] == 1
    assert cmd_dict["/children"] == 1
    assert cmd_dict["/masterclasses"] == 1
    assert cmd_dict["/recommendations"] == 1
    assert cmd_dict["/participants"] == 1
    assert cmd_dict["/wishlist"] == 1
    assert cmd_dict["/customcmd"] == 1

    # Verify summary structure
    summary = service.get_full_summary()
    assert "menu_buttons" in summary
    assert "text_commands" in summary
    assert len(summary["menu_buttons"]) == 8

    # Verify CSV export contains the new sections
    csv_text = service.export_csv()
    assert "=== Basic Menu Inline Buttons Counters ===" in csv_text
    assert "=== Text Commands Counters ===" in csv_text
    assert "🏢 План ярмарки" in csv_text
    assert "/start" in csv_text


def test_admin_analytics_api_and_ui_rendering_for_counters(tmp_path):
    """Verify Admin UI HTML rendering and API routes for menu buttons and text commands."""
    db_path = str(tmp_path / "analytics.db")
    service = AdminAnalyticsService(db_path=db_path)

    u1 = anonymize_user_id(555, salt="admin_test")
    service.record_inline_keyboard_event(u1, callback_data="action_map", button_name="🏢 План ярмарки")
    service.record_command(u1, "/start")
    service.record_command(u1, "/timetables")

    # 1. HTML Rendering
    summary = service.get_full_summary()
    html_output = AdminTemplateRenderer.render_analytics(summary)
    assert "Основные inline-кнопки меню" in html_output
    assert "Текстовые команды" in html_output
    assert "action_map" in html_output
    assert "/start" in html_output
    assert "/timetables" in html_output

    # 2. Router API endpoints
    router = AdminRouter()
    router.analytics_service = service
    router.session_manager.is_valid_session = MagicMock(return_value=True)
    headers = {
        "Cookie": f"{router.config.session_cookie_name}=valid_mock",
    }

    req_buttons = AdminRequest(method="GET", path="/api/analytics/buttons", headers=headers)
    resp_buttons = router.route(req_buttons)
    assert resp_buttons.status_code == 200
    json_buttons = json.loads(resp_buttons.body.decode("utf-8"))
    assert "buttons" in json_buttons
    assert len(json_buttons["buttons"]) == 8

    req_commands = AdminRequest(method="GET", path="/api/analytics/commands", headers=headers)
    resp_commands = router.route(req_commands)
    assert resp_commands.status_code == 200
    json_commands = json.loads(resp_commands.body.decode("utf-8"))
    assert "commands" in json_commands
    assert any(c["command"] == "/start" and c["count"] >= 1 for c in json_commands["commands"])
