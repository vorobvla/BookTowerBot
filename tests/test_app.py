"""Tests for app building, configuration, and handler registration."""

import os
from unittest.mock import patch

from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
)

from bot.app import build_application, setup_handlers
from bot.config import Config, PROJECT_ROOT


def test_config_from_env_default():
    with patch.dict(os.environ, {}, clear=True):
        config = Config.from_env()
        assert config.bot_token == ""


def test_config_from_env_with_token():
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token_123"}, clear=True):
        config = Config.from_env()
        assert config.bot_token == "test_token_123"


def test_project_root_relative_path():
    assert PROJECT_ROOT.is_dir()
    assert (PROJECT_ROOT / "main.py").is_file()


def test_build_application_registers_handlers():
    app = build_application("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    handlers = app.handlers[0]

    command_handlers = [h for h in handlers if isinstance(h, CommandHandler)]
    callback_handlers = [h for h in handlers if isinstance(h, CallbackQueryHandler)]
    message_handlers = [h for h in handlers if isinstance(h, MessageHandler)]

    registered_commands = set()
    for ch in command_handlers:
        registered_commands.update(ch.commands)

    assert "start" in registered_commands
    assert "help" in registered_commands
    assert "map" in registered_commands
    assert "timetables" in registered_commands
    assert "recommendations" in registered_commands
    assert "recs" in registered_commands

    assert len(callback_handlers) >= 1
    assert len(message_handlers) >= 1


def test_build_application_concurrent_updates():
    app = build_application("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    assert app.update_processor.max_concurrent_updates > 1
