"""Children Activity section for festival timetable and events flagged as children activities."""

import logging
from typing import Optional
from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.content import BTN_CHILDREN_ACTIVITY, CHILDREN_ACTIVITY_MESSAGE
from bot.keyboards import CB_CHILDREN_ACTIVITY
from bot.sections.base import BaseSection
from bot.timetable.keyboards import (
    CB_CA_DATES,
    CB_CA_DATE_PREFIX,
    CB_CA_LOC_PREFIX,
    get_dates_inline_keyboard,
    get_locations_inline_keyboard,
    get_timetable_details_keyboard,
)
from bot.timetable.service import TimetableService

logger = logging.getLogger(__name__)


class ChildrenActivity(BaseSection):
    """Children Activity section delivering events flagged as children activities."""

    name = "children"
    commands = ["children", "children_activity", "kids", "child"]
    button_text = BTN_CHILDREN_ACTIVITY
    callback_data = CB_CHILDREN_ACTIVITY
    aliases = {
        "детская программа",
        "детская",
        "дети",
        "children",
        "children_activity",
        "kids",
        "child",
        "/children",
        "/children_activity",
        "/kids",
        "/child",
        "🎈 детская программа",
    }
    use_reply_keyboard = False

    def __init__(self, service: Optional[TimetableService] = None):
        self.service = service or TimetableService()

    def get_text_content(self) -> str:
        """Return introductory text for children activity section."""
        return CHILDREN_ACTIVITY_MESSAGE

    def get_display_text(self) -> str:
        """Generate formatted overview text with available children activity dates."""
        dates = self.service.get_available_dates(children_only=True)
        if not dates:
            return self.get_text_content()
        formatted_dates = [f"• {self.service.format_date_label(d)}" for d in dates]
        return f"{self.get_text_content()}\n\n" + "\n".join(formatted_dates)

    def get_reply_markup(self, inline: bool = False):
        """Generate inline date selector keyboard for children activities."""
        dates = self.service.get_available_dates(children_only=True)
        return get_dates_inline_keyboard(
            dates=dates,
            date_formatter=self.service.format_date_label,
            date_prefix=CB_CA_DATE_PREFIX,
        )

    def matches_callback(self, callback_data: str) -> bool:
        """Check if callback query belongs to children activity section."""
        return (
            callback_data == self.callback_data
            or callback_data == CB_CA_DATES
            or callback_data.startswith(CB_CA_DATE_PREFIX)
            or callback_data.startswith(CB_CA_LOC_PREFIX)
        )

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle command or direct entry for children activity section."""
        if update.effective_message:
            await self.send_response(
                update.effective_message,
                inline=(not self.use_reply_keyboard),
            )

    async def send_response(self, target: Message, inline: Optional[bool] = None) -> None:
        """Send children activity section entry point."""
        await target.reply_text(
            text=self.get_text_content(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_reply_markup(inline=True),
        )

    async def handle_callback_query(self, query) -> None:
        """Handle inline button clicks within children activity navigation."""
        data = query.data

        if data == self.callback_data or data == CB_CA_DATES:
            await self._show_dates(query)
        elif data.startswith(CB_CA_DATE_PREFIX):
            date_str = data[len(CB_CA_DATE_PREFIX):]
            await self._show_locations(query, date_str)
        elif data.startswith(CB_CA_LOC_PREFIX):
            payload = data[len(CB_CA_LOC_PREFIX):]
            if ":" in payload:
                date_str, location = payload.split(":", 1)
                await self._show_timetable(query, date_str, location)
            else:
                await self._show_dates(query)
        else:
            await self._show_dates(query)

    async def _show_dates(self, query) -> None:
        """Display list of available children activity dates."""
        markup = self.get_reply_markup(inline=True)
        await self._edit_or_reply(query, self.get_text_content(), markup)

    async def _show_locations(self, query, date_str: str) -> None:
        """Display locations with children activities for a chosen date."""
        locations = self.service.get_locations(date_str, children_only=True)
        date_label = self.service.format_date_label(date_str)
        if not locations:
            text = f"🎈 *{date_label}*\n\nНа выбранную дату детских мероприятий не запланировано."
            markup = self.get_reply_markup(inline=True)
        else:
            text = f"📍 *Выберите площадку детской программы на {date_label}:*"
            markup = get_locations_inline_keyboard(
                date_str,
                locations,
                loc_prefix=CB_CA_LOC_PREFIX,
                back_cb=self.callback_data,
            )

        await self._edit_or_reply(query, text, markup)

    async def _show_timetable(self, query, date_str: str, location: str) -> None:
        """Display scheduled children activity events for chosen date and location."""
        text = self.service.format_timetable(date_str, location, children_only=True)
        markup = get_timetable_details_keyboard(
            date_str,
            date_prefix=CB_CA_DATE_PREFIX,
            back_cb=self.callback_data,
        )
        await self._edit_or_reply(query, text, markup)

    async def _edit_or_reply(self, query, text: str, markup) -> None:
        """Edit current message if possible, otherwise send a new one."""
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


ChildrenActivitySection = ChildrenActivity
