"""Main entry point for running BookTowerBot."""

import argparse
import asyncio
import logging
import sys

from bot.config import Config
from bot.app import build_application
from bot.content import (
    BTN_HELP,
    BTN_MAP,
    BTN_RECOMMENDATIONS,
    BTN_TIMETABLE,
    START_MESSAGE,
    UNKNOWN_COMMAND_MESSAGE,
)
from bot.sections import default_registry

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def run_local_interactive_cli() -> None:
    """Run an interactive local CLI simulation of the bot for local testing."""
    print("==================================================")
    print(" 📚 BookTowerBot - Local Simulation Mode")
    print("==================================================")
    print("Simulating bot interactions in the terminal.")
    print("Available simulated inputs:")
    print("  Commands: /start, /map, /timetables, /recommendations, /help")
    print(f"  Buttons:  '{BTN_MAP}', '{BTN_TIMETABLE}', '{BTN_RECOMMENDATIONS}', '{BTN_HELP}'")
    print("Type 'exit' or 'quit' to end simulation.\n")

    # Initial start message
    print(f"[Bot]:\n{START_MESSAGE}\n")
    print(f"[Buttons Available]: [{BTN_MAP}] [{BTN_TIMETABLE}] [{BTN_RECOMMENDATIONS}] [{BTN_HELP}]\n")

    while True:
        try:
            user_input = input("[You] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting local simulation.")
            break

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("Ending local simulation.")
            break

        section = default_registry.find_by_text(user_input) or default_registry.find_by_command(user_input)
        if section:
            print(f"\n[Bot]:\n{section.get_display_text()}\n")
        else:
            print(f"\n[Bot]:\n{UNKNOWN_COMMAND_MESSAGE}\n")


def main() -> None:
    """Parse arguments and start the bot or local simulation."""
    parser = argparse.ArgumentParser(description="BookTowerBot")
    parser.add_argument(
        "--token",
        type=str,
        default="",
        help="Telegram Bot API Token (overrides TELEGRAM_BOT_TOKEN environment variable)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run local interactive CLI simulation without connecting to Telegram servers",
    )
    parser.add_argument(
        "--assetsPath",
        type=str,
        default=".assets",
        help="Path to the assets directory (overrides ASSETS_PATH environment variable)",
    )

    args = parser.parse_args()

    if args.local:
        run_local_interactive_cli()
        return

    config = Config.from_env()
    token = args.token.strip() or config.bot_token

    if not token:
        logger.warning("No TELEGRAM_BOT_TOKEN provided.")
        print(
            "\n[Notice] No Telegram bot token specified!\n"
            "To run the live bot:\n"
            "  export TELEGRAM_BOT_TOKEN='your_token_here'\n"
            "  python main.py\n"
            "Or run directly with:\n"
            "  python main.py --token 'your_token_here'\n\n"
            "To test locally right now without a token, use:\n"
            "  python main.py --local\n"
            "Or run the automated unit test suite with:\n"
            "  pytest\n"
        )
        sys.exit(1)

    logger.info("Starting BookTowerBot...")
    app = build_application(token)
    app.run_polling()


if __name__ == "__main__":
    main()
