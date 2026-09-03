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
    assert (PROJECT_ROOT / "bot" / "__main__.py").is_file()


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
    assert "children" in registered_commands
    assert "children_activity" in registered_commands
    assert "kids" in registered_commands
    assert "recommendations" in registered_commands
    assert "recs" in registered_commands
    assert "participants" in registered_commands
    assert "stands" in registered_commands
    assert "vendors" in registered_commands

    assert len(callback_handlers) >= 1
    assert len(message_handlers) >= 1


def test_build_application_concurrent_updates():
    app = build_application("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    assert app.update_processor.max_concurrent_updates > 1


def test_bot_main_local():
    from bot.__main__ import main as bot_main
    with patch("sys.argv", ["bot", "--local"]), patch("bot.__main__.run_local_interactive_cli") as mock_cli:
        bot_main()
        mock_cli.assert_called_once()


def test_bot_main_no_token():
    import pytest
    from bot.__main__ import main as bot_main
    with patch("sys.argv", ["bot"]), patch.dict(os.environ, {}, clear=True):
        with pytest.raises(SystemExit) as exc_info:
            bot_main()
        assert exc_info.value.code == 1


def test_bot_main_with_token():
    from bot.__main__ import main as bot_main
    with patch("sys.argv", ["bot", "--token", "test_tok"]), patch("bot.__main__.build_application") as mock_build_app:
        mock_app = mock_build_app.return_value
        bot_main()
        mock_build_app.assert_called_once_with("test_tok")
        mock_app.run_polling.assert_called_once()


def test_root_main_launches_modules():
    import sys
    from unittest.mock import MagicMock
    from main import main as root_main

    mock_admin_proc = MagicMock()
    mock_admin_proc.poll.return_value = 0
    mock_admin_proc.returncode = 0

    mock_bot_proc = MagicMock()
    mock_bot_proc.poll.return_value = 0
    mock_bot_proc.returncode = 0

    def mock_popen(cmd, *args, **kwargs):
        if "-m" in cmd and "admin" in cmd:
            return mock_admin_proc
        return mock_bot_proc

    with patch("sys.argv", ["main.py", "--local"]), \
         patch("subprocess.Popen", side_effect=mock_popen) as mock_popen_call, \
         patch("sys.exit") as mock_exit:
        root_main()
        assert mock_popen_call.call_count == 2
        mock_exit.assert_called_once_with(0)


def test_root_main_passes_proper_arguments():
    import sys
    from unittest.mock import MagicMock
    from main import main as root_main

    mock_admin_proc = MagicMock()
    mock_admin_proc.poll.return_value = 0
    mock_admin_proc.returncode = 0

    mock_bot_proc = MagicMock()
    mock_bot_proc.poll.return_value = 0
    mock_bot_proc.returncode = 0

    recorded_cmds = []

    def mock_popen(cmd, *args, **kwargs):
        recorded_cmds.append(cmd)
        if "-m" in cmd and "admin" in cmd:
            return mock_admin_proc
        return mock_bot_proc

    cli_args = [
        "main.py",
        "--token", "my_bot_token",
        "--local",
        "--host", "127.0.0.1",
        "--port", "9090",
        "--auth-db-path", "/custom/auth.db",
        "--assets-path", "/custom/assets",
    ]

    with patch("sys.argv", cli_args), \
         patch("subprocess.Popen", side_effect=mock_popen), \
         patch("sys.exit"):
        root_main()

    assert len(recorded_cmds) == 2
    admin_cmd = recorded_cmds[0]
    bot_cmd = recorded_cmds[1]

    assert admin_cmd == [
        sys.executable, "-m", "admin",
        "--host", "127.0.0.1",
        "--port", "9090",
        "--auth-db-path", "/custom/auth.db",
        "--assets-path", "/custom/assets",
    ]

    assert bot_cmd == [
        sys.executable, "-m", "bot",
        "--token", "my_bot_token",
        "--local",
        "--assets-path", "/custom/assets",
    ]


def test_admin_main_parses_arguments():
    from admin.__main__ import main as admin_main
    with patch("sys.argv", [
        "admin",
        "--host", "127.0.0.1",
        "--port", "8888",
        "--auth-db-path", ":memory:",
        "--assets-path", "/tmp/test_assets",
    ]), patch("admin.__main__.AdminApp") as mock_admin_app_cls:
        mock_instance = mock_admin_app_cls.return_value
        admin_main()
        mock_admin_app_cls.assert_called_once()
        config = mock_admin_app_cls.call_args[0][0]
        assert config.host == "127.0.0.1"
        assert config.port == 8888
        assert config.auth_db_path == ":memory:"
        assert config.assets_path == "/tmp/test_assets"
        mock_instance.run.assert_called_once_with(background=False)
