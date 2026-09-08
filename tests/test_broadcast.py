"""Tests for broadcast registry, broadcast service, loopback API, and Admin broadcast features."""

import asyncio
import json
import os
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from bot.broadcast.registry import ChatRegistry, default_chat_registry
from bot.broadcast.service import AVAILABLE_BROADCAST_COMMANDS, BroadcastService
from bot.content import CB_MAP, CB_TIMETABLE, CB_WISHLIST_GET
from bot.handlers import (
    button_callback_handler,
    help_handler,
    map_handler,
    photo_message_handler,
    start_handler,
    text_message_handler,
    timetable_handler,
    wishlist_handler,
)
from bot.sections.registry import SectionRegistry, default_registry
from bot.wishlist.service import WishlistService, get_user_id


def test_chat_registry_operations():
    """Verify in-memory ChatRegistry registration, deduplication, counting, unregistering, and clearing."""
    registry = ChatRegistry()
    assert registry.count() == 0
    assert registry.get_all() == []

    # Register new chats
    assert registry.register(1001) is True
    assert registry.register(1002) is True
    assert registry.count() == 2
    assert registry.is_registered(1001) is True
    assert registry.is_registered(9999) is False

    # Duplicate registration
    assert registry.register(1001) is False
    assert registry.count() == 2

    # String chat ID conversion
    assert registry.register("1003") is True
    assert registry.is_registered(1003) is True
    assert registry.count() == 3

    # Invalid ID
    assert registry.register("invalid") is False
    assert registry.count() == 3

    # Unregister
    assert registry.unregister(1002) is True
    assert registry.unregister(9999) is False
    assert registry.count() == 2
    assert set(registry.get_all()) == {1001, 1003}

    # Clear
    registry.clear()
    assert registry.count() == 0
    assert registry.get_all() == []


@pytest.mark.asyncio
async def test_bot_handlers_register_chat_id():
    """Verify that user updates handled in bot/handlers.py register chat IDs in default_chat_registry."""
    default_chat_registry.clear()
    assert default_chat_registry.count() == 0

    # 1. /start command
    update_start = MagicMock()
    update_start.effective_chat.id = 1111
    update_start.effective_user.id = 1111
    update_start.effective_message.reply_text = AsyncMock()
    context = MagicMock()

    await start_handler(update_start, context)
    assert default_chat_registry.is_registered(1111) is True
    assert default_chat_registry.count() == 1

    # 2. /timetables command with another chat
    update_tt = MagicMock()
    update_tt.effective_chat.id = 2222
    update_tt.effective_user.id = 2222
    update_tt.effective_message.reply_text = AsyncMock()

    await timetable_handler(update_tt, context)
    assert default_chat_registry.is_registered(2222) is True
    assert default_chat_registry.count() == 2

    # 3. Callback query with another chat
    update_cb = MagicMock()
    update_cb.effective_chat.id = 3333
    update_cb.effective_user.id = 3333
    update_cb.callback_query.data = CB_MAP
    update_cb.callback_query.answer = AsyncMock()
    update_cb.callback_query.message.reply_text = AsyncMock()

    await button_callback_handler(update_cb, context)
    assert default_chat_registry.is_registered(3333) is True
    assert default_chat_registry.count() == 3

    # 4. Text message with another chat
    update_text = MagicMock()
    update_text.effective_chat.id = 4444
    update_text.effective_user.id = 4444
    update_text.effective_message.text = "Расписание"
    update_text.effective_message.reply_text = AsyncMock()

    await text_message_handler(update_text, context)
    assert default_chat_registry.is_registered(4444) is True
    assert default_chat_registry.count() == 4


@pytest.mark.asyncio
async def test_broadcast_message_dispatch():
    """Verify BroadcastService.broadcast_message sends messages to all registered chats and handles errors."""
    registry = ChatRegistry()
    registry.register(101)
    registry.register(102)
    registry.register(103)

    mock_bot = MagicMock()
    async def mock_send_message(chat_id, text, parse_mode=None, reply_markup=None):
        if chat_id == 102:
            raise Exception("Chat blocked by user")
        return MagicMock()

    mock_bot.send_message = AsyncMock(side_effect=mock_send_message)

    service = BroadcastService(bot=mock_bot, registry=registry, rate_limit_delay=0)
    result = await service.broadcast_message(text="Внимание! Начало через 10 минут.")

    assert result["status"] == "ok"
    assert result["total_chats"] == 3
    assert result["sent_count"] == 2
    assert result["failed_count"] == 1
    assert len(result["errors"]) == 1
    assert result["errors"][0]["chat_id"] == 102
    assert "blocked" in result["errors"][0]["error"]
    assert mock_bot.send_message.call_count == 3


@pytest.mark.asyncio
async def test_broadcast_command_standard_section():
    """Verify BroadcastService.broadcast_command resolves section commands and sends content with markup."""
    registry = ChatRegistry()
    registry.register(201)
    registry.register(202)

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    service = BroadcastService(bot=mock_bot, registry=registry, rate_limit_delay=0)
    result = await service.broadcast_command("timetables")

    assert result["status"] == "ok"
    assert result["total_chats"] == 2
    assert result["sent_count"] == 2
    assert result["failed_count"] == 0
    assert mock_bot.send_message.call_count == 2

    # Check that the sent message contains timetable text and reply markup
    first_call_args = mock_bot.send_message.call_args_list[0]
    assert "Расписание" in first_call_args.kwargs["text"]
    assert first_call_args.kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_broadcast_command_wishlist_personal(tmp_path, monkeypatch):
    """Verify BroadcastService.broadcast_command('wishlist_get') generates personalized wishlist text per user."""
    monkeypatch.setenv("WISHLIST_SALT", "test_broadcast_salt")
    db_path = str(tmp_path / "test_wishlist.db")
    wishlist_service = WishlistService(db_path=db_path)

    chat_a = 5001
    chat_b = 5002

    user_a = get_user_id(chat_a)
    user_b = get_user_id(chat_b)

    wishlist_service.add_book(user_a, title="Книга Пользователя А", authors="Автор 1")

    registry = ChatRegistry()
    registry.register(chat_a)
    registry.register(chat_b)

    sent_messages = {}
    mock_bot = MagicMock()
    async def mock_send(chat_id, text, parse_mode=None, reply_markup=None):
        sent_messages[chat_id] = text
        return MagicMock()

    mock_bot.send_message = AsyncMock(side_effect=mock_send)

    service = BroadcastService(
        bot=mock_bot,
        registry=registry,
        wishlist_service=wishlist_service,
        rate_limit_delay=0,
    )
    result = await service.broadcast_command("wishlist_get")

    assert result["status"] == "ok"
    assert result["total_chats"] == 2
    assert result["sent_count"] == 2

    assert "Книга Пользователя А" in sent_messages[chat_a]
    assert "Ваш вишлист пока пуст" in sent_messages[chat_b]


@pytest.mark.asyncio
async def test_composite_broadcast():
    """Verify composite broadcast delivers both message and command sequentially."""
    registry = ChatRegistry()
    registry.register(6001)

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    service = BroadcastService(bot=mock_bot, registry=registry, rate_limit_delay=0)
    result = await service.broadcast(
        text="Срочное объявление!",
        command="help",
    )

    assert result["status"] == "ok"
    assert result["total_chats"] == 1
    assert result["sent_count"] == 1
    assert mock_bot.send_message.call_count == 2
    assert mock_bot.send_message.call_args_list[0].kwargs["text"] == "Срочное объявление!"
    assert "Помощь" in mock_bot.send_message.call_args_list[1].kwargs["text"]


@pytest.mark.asyncio
async def test_broadcast_unknown_command_and_empty_inputs():
    """Verify BroadcastService returns descriptive error responses for unknown commands or empty input."""
    registry = ChatRegistry()
    registry.register(7001)

    mock_bot = MagicMock()
    service = BroadcastService(bot=mock_bot, registry=registry, rate_limit_delay=0)

    # Empty broadcast
    res_empty = await service.broadcast()
    assert res_empty["status"] == "error"

    # Unknown command
    res_unknown = await service.broadcast_command("nonexistent_command_xyz")
    assert res_unknown["status"] == "error"
    assert "Unknown command" in res_unknown["errors"][0]["error"]


def test_bot_internal_server_endpoints():
    """Verify internal loopback HTTP server endpoints (chat count, commands, message, command, broadcast)."""
    import json
    import urllib.request
    import urllib.error
    from bot.broadcast.server import BotInternalServer

    registry = ChatRegistry()
    registry.register(8001)
    registry.register(8002)

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.send_photo = AsyncMock()

    service = BroadcastService(bot=mock_bot, registry=registry, rate_limit_delay=0)
    server = BotInternalServer(broadcast_service=service, host="127.0.0.1", port=0)
    server.start(background=True)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"

    try:
        # 1. GET /internal/chats/count
        with urllib.request.urlopen(f"{base_url}/internal/chats/count", timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert data["chat_count"] == 2

        # 2. GET /internal/commands
        with urllib.request.urlopen(f"{base_url}/internal/commands", timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert isinstance(data["commands"], list)
            assert any(cmd["command"] == "timetables" for cmd in data["commands"])
            assert any(cmd["command"] == "wishlist_get" for cmd in data["commands"])

        # 3. POST /internal/broadcast/message
        req_msg = urllib.request.Request(
            f"{base_url}/internal/broadcast/message",
            data=json.dumps({"text": "Привет всем!"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_msg, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert data["total_chats"] == 2
            assert data["sent_count"] == 2

        # 4. POST /internal/broadcast/command
        req_cmd = urllib.request.Request(
            f"{base_url}/internal/broadcast/command",
            data=json.dumps({"command": "map"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_cmd, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert data["total_chats"] == 2
            assert data["sent_count"] == 2

        # 5. POST /internal/broadcast (composite)
        req_comp = urllib.request.Request(
            f"{base_url}/internal/broadcast",
            data=json.dumps({"text": "Важное сообщение", "command": "children"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_comp, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert data["total_chats"] == 2
            assert data["sent_count"] == 2

        # 6. GET /internal/unknown (404)
        try:
            urllib.request.urlopen(f"{base_url}/internal/nonexistent", timeout=5)
            assert False, "Should raise 404 HTTPError"
        except urllib.error.HTTPError as e:
            assert e.code == 404

    finally:
        server.stop()


def test_admin_broadcast_service_and_routes(tmp_path):
    """Verify AdminBroadcastService, AdminTemplateRenderer, and AdminRouter broadcast endpoints."""
    from admin.auth.authenticator import AdminAuthenticator
    from admin.auth.session_manager import AdminSessionManager
    from admin.config import AdminConfig
    from admin.server.request import AdminRequest
    from admin.server.router import AdminRouter
    from admin.services.broadcast_service import AdminBroadcastService
    from admin.views.template_renderer import AdminTemplateRenderer
    from bot.broadcast.server import BotInternalServer

    # 1. Start Bot Internal Loopback server on ephemeral port
    registry = ChatRegistry()
    registry.register(9001)
    registry.register(9002)

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.send_photo = AsyncMock()

    bot_service = BroadcastService(bot=mock_bot, registry=registry, rate_limit_delay=0)
    server = BotInternalServer(broadcast_service=bot_service, host="127.0.0.1", port=0)
    server.start(background=True)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"

    try:
        # 2. Test AdminBroadcastService
        admin_broadcast_svc = AdminBroadcastService(api_url=base_url)
        status = admin_broadcast_svc.get_status()
        assert status["online"] is True
        assert status["chat_count"] == 2
        assert admin_broadcast_svc.get_chat_count() == 2

        cmds = admin_broadcast_svc.get_available_commands()
        assert isinstance(cmds, list)
        assert len(cmds) > 0

        # Broadcast via Admin service
        res_svc_msg = admin_broadcast_svc.broadcast_message("Тестовое сообщение")
        assert res_svc_msg["status"] == "ok"
        assert res_svc_msg["sent_count"] == 2

        # 3. Test Template Rendering
        rendered_html = AdminTemplateRenderer.render_broadcast(
            chat_count=2,
            commands=cmds,
            is_bot_online=True,
            message="Рассылка успешно выполнена!",
        )
        assert "Рассылка пользователям" in rendered_html
        assert "Рассылка успешно выполнена!" in rendered_html
        assert "broadcastConfirmModal" in rendered_html

        # 4. Test AdminRouter with authenticated session
        auth_db = str(tmp_path / "test_admin.db")
        config = AdminConfig(
            auth_db_path=auth_db,
            bot_internal_api_url=base_url,
        )
        authenticator = AdminAuthenticator(config)
        authenticator.register("admin", "secret123")
        conn = sqlite3.connect(auth_db)
        conn.execute("UPDATE admin_users SET is_confirmed = 1 WHERE username = 'admin'")
        conn.commit()
        conn.close()

        session_mgr = AdminSessionManager(timeout_seconds=3600)
        token = session_mgr.create_session()
        headers = {
            "Cookie": f"{config.session_cookie_name}={token}",
            "Host": "localhost:8080",
        }

        router = AdminRouter(
            config=config,
            authenticator=authenticator,
            session_manager=session_mgr,
            broadcast_service=admin_broadcast_svc,
        )

        # GET /broadcast
        req_get = AdminRequest(method="GET", path="/broadcast", headers=headers)
        res_get = router.route(req_get)
        assert res_get.status_code == 200
        # assert "Рассылка" in res_get.body.decode("utf-8")
        # assert "Активных чатов " in res_get.body.decode("utf-8")

        import urllib.parse

        # POST /broadcast/send
        body_send = urllib.parse.urlencode({"text": "Срочное оповещение", "command": "timetables"}).encode("utf-8")
        req_post_send = AdminRequest(
            method="POST",
            path="/broadcast/send",
            headers={"Content-Type": "application/x-www-form-urlencoded", **headers},
            body=body_send,
        )
        res_post_send = router.route(req_post_send)
        assert res_post_send.status_code == 302
        assert "/broadcast?msg=" in res_post_send.headers.get("Location", "")

        # POST /broadcast/message
        body_msg = urllib.parse.urlencode({"text": "Только сообщение"}).encode("utf-8")
        req_post_msg = AdminRequest(
            method="POST",
            path="/broadcast/message",
            headers={"Content-Type": "application/x-www-form-urlencoded", **headers},
            body=body_msg,
        )
        res_post_msg = router.route(req_post_msg)
        assert res_post_msg.status_code == 302
        assert "/broadcast?msg=" in res_post_msg.headers.get("Location", "")

        # POST /broadcast/command
        body_cmd = urllib.parse.urlencode({"command": "map"}).encode("utf-8")
        req_post_cmd = AdminRequest(
            method="POST",
            path="/broadcast/command",
            headers={"Content-Type": "application/x-www-form-urlencoded", **headers},
            body=body_cmd,
        )
        res_post_cmd = router.route(req_post_cmd)
        assert res_post_cmd.status_code == 302
        assert "/broadcast?msg=" in res_post_cmd.headers.get("Location", "")

        # GET /api/broadcast/status
        req_api_status = AdminRequest(method="GET", path="/api/broadcast/status", headers=headers)
        res_api_status = router.route(req_api_status)
        assert res_api_status.status_code == 200
        assert '"chat_count": 2' in res_api_status.body.decode("utf-8")

        # GET /api/broadcast/commands
        req_api_cmds = AdminRequest(method="GET", path="/api/broadcast/commands", headers=headers)
        res_api_cmds = router.route(req_api_cmds)
        assert res_api_cmds.status_code == 200
        assert '"timetables"' in res_api_cmds.body.decode("utf-8")

        # POST /api/broadcast/send
        req_api_send = AdminRequest(
            method="POST",
            path="/api/broadcast/send",
            headers={"Content-Type": "application/json", **headers},
            body=json.dumps({"text": "API сообщение", "command": "help"}).encode("utf-8"),
        )
        res_api_send = router.route(req_api_send)
        assert res_api_send.status_code == 200
        assert '"sent_count": 2' in res_api_send.body.decode("utf-8")

    finally:
        server.stop()
