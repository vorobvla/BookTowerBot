"""Timetable section for event schedules and sessions."""

from typing import List, Optional
from telegram import Message
from telegram.constants import ParseMode

from bot.content import BTN_TIMETABLE, TIMETABLE_MESSAGE
from bot.keyboards import CB_TIMETABLE
from bot.sections.base import BaseSection
from bot.timetable.keyboards import (
    CB_TT_DATES,
    CB_TT_DATE_PREFIX,
    CB_TT_LOC_PREFIX,
    get_dates_inline_keyboard,
    get_locations_inline_keyboard,
    get_timetable_details_keyboard,
)
from bot.timetable.service import TimetableService


class Timetable(BaseSection):
    """Timetable section handling event schedules, date choices, and locations."""

    name = "timetables"
    commands = ["timetables", "timetable", "schedule"]
    button_text = BTN_TIMETABLE
    callback_data = CB_TIMETABLE
    aliases = {
        "расписание",
        "программа",
        "timetable",
        "timetables",
        "schedule",
        "time table",
        "/timetables",
        "/timetable",
        "/schedule",
    }
    use_reply_keyboard = False

    def __init__(self, service: Optional[TimetableService] = None):
        self.service = service or TimetableService()

    def get_text_content(self) -> str:
        return TIMETABLE_MESSAGE

    def get_display_text(self) -> str:
        dates = self.service.get_available_dates()
        if not dates:
            return self.get_text_content()
        formatted_dates = [f"• {self.service.format_date_label(d)}" for d in dates]
        return f"{self.get_text_content()}\n\n" + "\n".join(formatted_dates)

    def get_reply_markup(self, inline: bool = False):
        dates = self.service.get_available_dates()
        return get_dates_inline_keyboard(
            dates=dates,
            date_formatter=self.service.format_date_label,
        )

    def matches_callback(self, callback_data: str) -> bool:
        """Check whether callback data belongs to the timetable navigation flow."""
        return (
            callback_data == self.callback_data
            or callback_data == CB_TT_DATES
            or callback_data.startswith(CB_TT_DATE_PREFIX)
            or callback_data.startswith(CB_TT_LOC_PREFIX)
        )

    async def send_response(self, target: Message, inline: Optional[bool] = None) -> None:
        """Send timetable initial response with date selection buttons."""
        await target.reply_text(
            text=self.get_text_content(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_reply_markup(inline=True),
        )

    async def handle_callback_query(self, query) -> None:
        """Handle multi-step interactive inline timetable callbacks."""
        data = query.data

        if data == self.callback_data or data == CB_TT_DATES:
            await self._show_dates(query)
        elif data.startswith(CB_TT_DATE_PREFIX):
            date_str = data[len(CB_TT_DATE_PREFIX):]
            await self._show_locations(query, date_str)
        elif data.startswith(CB_TT_LOC_PREFIX):
            payload = data[len(CB_TT_LOC_PREFIX):]
            if ":" in payload:
                date_str, location = payload.split(":", 1)
                await self._show_timetable(query, date_str, location)
            else:
                await self._show_dates(query)
        else:
            await self._show_dates(query)

    async def _show_dates(self, query) -> None:
        markup = self.get_reply_markup(inline=True)
        await self._edit_or_reply(query, self.get_text_content(), markup)

    async def _show_locations(self, query, date_str: str) -> None:
        locations = self.service.get_locations(date_str)
        date_label = self.service.format_date_label(date_str)
        if not locations:
            text = f"📅 *{date_label}*\n\nНа выбранную дату событий не запланировано."
            markup = self.get_reply_markup(inline=True)
        else:
            text = f"📍 *Выберите площадку на {date_label}:*"
            markup = get_locations_inline_keyboard(date_str, locations)

        await self._edit_or_reply(query, text, markup)

    async def _show_timetable(self, query, date_str: str, location: str) -> None:
        text = self.service.format_timetable(date_str, location)
        markup = get_timetable_details_keyboard(date_str)
        await self._edit_or_reply(query, text, markup)

    async def _edit_or_reply(self, query, text: str, markup) -> None:
        if hasattr(query, "edit_message_text") and callable(query.edit_message_text):
            try:
                await query.edit_message_text(
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=markup,
                )
                return
            except Exception:
                pass

        if getattr(query, "message", None):
            await query.message.reply_text(
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=markup,
            )


TimetableSection = Timetable
