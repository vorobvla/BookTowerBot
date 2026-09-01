"""Telegram bot command, message, and callback handlers."""

import logging
import os
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.content import (
    BTN_HELP,
    BTN_MAP,
    BTN_RECOMMENDATIONS,
    BTN_TIMETABLE,
    HELP_MESSAGE,
    MAP_PATH,
    MAP_MESSAGE,
    RECOMMENDATIONS_MESSAGE,
    START_MESSAGE,
    TIMETABLE_MESSAGE,
    UNKNOWN_COMMAND_MESSAGE,
)
from bot.keyboards import (
    CB_HELP,
    CB_MAP,
    CB_RECOMMENDATIONS,
    CB_TIMETABLE,
    get_main_inline_keyboard,
    get_main_reply_keyboard,
)

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if update.effective_message:
        await update.effective_message.reply_text(
            text=START_MESSAGE,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_reply_keyboard(),
        )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if update.effective_message:
        await update.effective_message.reply_text(
            text=HELP_MESSAGE,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_reply_keyboard(),
        )


async def map_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /map command."""
    if update.effective_message:
        if os.path.exists(MAP_PATH):
            with open(MAP_PATH, "rb") as photo:
                await update.effective_message.reply_photo(
                    photo=photo,
                    caption=MAP_MESSAGE,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_main_inline_keyboard(),
                )
        else:
            await update.effective_message.reply_text(
                text=f"Map not found at {MAP_PATH}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_inline_keyboard(),
            )


async def timetable_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /timetable command."""
    if update.effective_message:
        await update.effective_message.reply_text(
            text=TIMETABLE_MESSAGE,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_inline_keyboard(),
        )


async def recommendations_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /recommendations and /recs commands."""
    if update.effective_message:
        await update.effective_message.reply_text(
            text=RECOMMENDATIONS_MESSAGE,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_inline_keyboard(),
        )


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callback queries."""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    action = query.data
    if action == CB_MAP:
        if os.path.exists(MAP_PATH):
            with open(MAP_PATH, "rb") as photo:
                await query.message.reply_photo(
                    photo=photo,
                    caption=MAP_MESSAGE,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_main_inline_keyboard(),
                )
        else:
            await query.message.reply_photo(
                photo=MAP_PATH,
                caption=MAP_MESSAGE,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_inline_keyboard(),
            )
        return

    response_map = {
        CB_TIMETABLE: TIMETABLE_MESSAGE,
        CB_RECOMMENDATIONS: RECOMMENDATIONS_MESSAGE,
        CB_HELP: HELP_MESSAGE,
    }

    text = response_map.get(action)
    if text:
        await query.message.reply_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_inline_keyboard(),
        )


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages matching reply keyboard buttons or custom input."""
    if not update.effective_message or not update.effective_message.text:
        return

    text = update.effective_message.text.strip()
    normalized = text.lower()

    if text == BTN_MAP or normalized in {"карта", "план", "схема", "map", "venue map", "venue"}:
        await map_handler(update, context)
    elif text == BTN_TIMETABLE or normalized in {"расписание", "программа", "timetable", "schedule", "time table"}:
        await timetable_handler(update, context)
    elif text == BTN_RECOMMENDATIONS or normalized in {"рекомендации", "recommendations", "recs", "recommendation"}:
        await recommendations_handler(update, context)
    elif text == BTN_HELP or normalized in {"помощь", "справка", "help", "info"}:
        await help_handler(update, context)
    else:
        await update.effective_message.reply_text(
            text=UNKNOWN_COMMAND_MESSAGE,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_reply_keyboard(),
        )
