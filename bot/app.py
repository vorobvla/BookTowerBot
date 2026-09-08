"""Telegram Bot application factory and setup."""

import asyncio
import logging
from typing import Optional
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.broadcast.server import BotInternalServer
from bot.broadcast.service import BroadcastService
from bot.handlers import (
    button_callback_handler,
    children_activity_handler,
    help_handler,
    map_handler,
    master_classes_handler,
    participants_handler,
    photo_message_handler,
    recommendations_handler,
    start_handler,
    text_message_handler,
    timetable_handler,
    wishlist_handler,
)

logger = logging.getLogger(__name__)


def setup_handlers(app: Application) -> None:
    """Register all bot handlers with the application."""
    # Command handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("map", map_handler))
    app.add_handler(CommandHandler(["timetables", "timetable", "schedule"], timetable_handler))
    app.add_handler(CommandHandler(["children", "children_activity", "kids"], children_activity_handler))
    app.add_handler(CommandHandler(["masterclasses", "masterclass", "mc", "master_classes"], master_classes_handler))
    app.add_handler(CommandHandler(["recommendations", "recs"], recommendations_handler))
    app.add_handler(CommandHandler(["participants", "stands", "stand", "vendors", "vendor", "part"], participants_handler))
    app.add_handler(CommandHandler(["wishlist", "getlist", "addbook", "editbook", "removebook", "deletebook", "isbn", "addisbn"], wishlist_handler))

    # Callback query handler for inline keyboard buttons
    app.add_handler(CallbackQueryHandler(button_callback_handler))

    # Photo message handler for barcode scanning
    app.add_handler(MessageHandler(filters.PHOTO, photo_message_handler))

    # Text message handler for reply keyboard buttons and regular text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))


def build_application(
    token: str,
    internal_host: str = "127.0.0.1",
    internal_port: int = 8085,
    enable_internal_server: bool = True,
) -> Application:
    """Build and configure the Telegram Bot Application with handlers and internal loopback server."""

    async def _post_init(app: Application) -> None:
        if enable_internal_server:
            try:
                loop = asyncio.get_running_loop()
                broadcast_svc = BroadcastService(bot=app.bot)
                server = BotInternalServer(
                    broadcast_service=broadcast_svc,
                    host=internal_host,
                    port=internal_port,
                    loop=loop,
                )
                server.start(background=True)
                app.bot_data["internal_server"] = server
                app.bot_data["broadcast_service"] = broadcast_svc
            except Exception as e:
                logger.error("Failed to start BotInternalServer: %s", e, exc_info=True)

    async def _post_shutdown(app: Application) -> None:
        server = app.bot_data.get("internal_server")
        if server:
            try:
                server.stop()
            except Exception as e:
                logger.debug("Error shutting down internal server: %s", e)

    builder = (
        ApplicationBuilder()
        .token(token)
        .concurrent_updates(True)
    )

    if enable_internal_server:
        builder = builder.post_init(_post_init).post_shutdown(_post_shutdown)

    app = builder.build()
    setup_handlers(app)
    return app
