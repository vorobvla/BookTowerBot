"""Main entry point for BookTower.

Starts both the admin panel and Telegram bot as Python modules.
"""

import argparse
import signal
import subprocess
import sys


def main() -> None:
    """Parse arguments and start admin and bot modules concurrently."""
    parser = argparse.ArgumentParser(
        description="BookTower - Central Launcher for Bot and Admin Console",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Telegram Bot API Token (overrides TELEGRAM_BOT_TOKEN environment variable)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run local interactive CLI simulation without connecting to Telegram servers",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Admin console host address to bind (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Admin console port to listen on (default: 8080)",
    )
    parser.add_argument(
        "--auth-db-path",
        "--authDbPath",
        dest="auth_db_path",
        type=str,
        default=None,
        help="Path to SQLite auth database",
    )
    parser.add_argument(
        "--assets-path",
        "--assetsPath",
        dest="assets_path",
        type=str,
        default=None,
        help="Path to the assets directory (overrides ASSETS_PATH environment variable)",
    )

    args = parser.parse_args()

    # Build argument list for admin module
    admin_cmd = [sys.executable, "-m", "admin"]
    if args.host:
        admin_cmd.extend(["--host", args.host])
    if args.port is not None:
        admin_cmd.extend(["--port", str(args.port)])
    if args.auth_db_path:
        admin_cmd.extend(["--auth-db-path", args.auth_db_path])
    if args.assets_path:
        admin_cmd.extend(["--assets-path", args.assets_path])

    # Build argument list for bot module
    bot_cmd = [sys.executable, "-m", "bot"]
    if args.token:
        bot_cmd.extend(["--token", args.token])
    if args.local:
        bot_cmd.append("--local")
    if args.assets_path:
        bot_cmd.extend(["--assets-path", args.assets_path])

    admin_process = subprocess.Popen(admin_cmd)
    bot_process = subprocess.Popen(bot_cmd)

    def shutdown_processes(*args) -> None:
        for proc in (admin_process, bot_process):
            if proc.poll() is None:
                proc.terminate()

    signal.signal(signal.SIGINT, shutdown_processes)
    signal.signal(signal.SIGTERM, shutdown_processes)

    # Wait for either process to exit
    while True:
        if admin_process.poll() is not None:
            if bot_process.poll() is None:
                bot_process.terminate()
            break
        if bot_process.poll() is not None:
            if admin_process.poll() is None:
                admin_process.terminate()
            break
        try:
            bot_process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            pass

    # Ensure all processes have stopped cleanly
    shutdown_processes()
    for proc in (admin_process, bot_process):
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()

    sys.exit(bot_process.returncode if bot_process.returncode is not None else 0)


if __name__ == "__main__":
    main()
