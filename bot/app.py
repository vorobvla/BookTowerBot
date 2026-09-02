"""Telegram Bot application factory and setup."""

import logging
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.handlers import (
    button_callback_handler,
    children_activity_handler,
    help_handler,
    map_handler,
    participants_handler,
    recommendations_handler,
    start_handler,
    text_message_handler,
    timetable_handler,
)

logger = logging.getLogger(__name__)


def setup_handlers(app: Application) -> None:
    """Register all bot handlers with the application."""
    # Command handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("map", map_handler))
    app.add_handler(CommandHandler("timetables", timetable_handler))
    app.add_handler(CommandHandler(["children", "children_activity", "kids"], children_activity_handler))
    app.add_handler(CommandHandler(["recommendations", "recs"], recommendations_handler))
    app.add_handler(CommandHandler(["participants", "stands", "vendors", "part"], participants_handler))

    # Callback query handler for inline keyboard buttons
    app.add_handler(CallbackQueryHandler(button_callback_handler))

    # Text message handler for reply keyboard buttons and regular text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))


def build_application(token: str) -> Application:
    """Build and configure the Telegram Bot Application."""
    app = (
        ApplicationBuilder()
        .token(token)
        .concurrent_updates(True)
        .build()
    )
    setup_handlers(app)
    return app
