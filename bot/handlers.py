"""Telegram bot command, message, and callback handlers."""

import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.content import UNKNOWN_COMMAND_MESSAGE
from bot.keyboards import get_main_reply_keyboard
from bot.sections import (
    Help,
    Map,
    Recommendations,
    Start,
    Timetable,
    default_registry,
)

logger = logging.getLogger(__name__)

# Section singletons
start_section = Start()
help_section = Help()
map_section = Map()
timetable_section = Timetable()
recommendations_section = Recommendations()


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await start_section.handle(update, context)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await help_section.handle(update, context)


async def map_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /map command."""
    await map_section.handle(update, context)


async def timetable_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /timetables command."""
    await timetable_section.handle(update, context)


async def recommendations_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /recommendations and /recs commands."""
    await recommendations_section.handle(update, context)


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callback queries."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    section = default_registry.find_by_callback(query.data)
    if section:
        if hasattr(section, "handle_callback_query"):
            await section.handle_callback_query(query)
        elif query.message:
            await section.send_response(query.message, inline=True)


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages matching reply keyboard buttons or custom input."""
    if not update.effective_message or not update.effective_message.text:
        return

    text = update.effective_message.text.strip()
    section = default_registry.find_by_text(text)
    if section:
        await section.send_response(
            update.effective_message,
            inline=(not section.use_reply_keyboard),
        )
    else:
        await update.effective_message.reply_text(
            text=UNKNOWN_COMMAND_MESSAGE,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_reply_keyboard(),
        )
