"""Master Classes section for festival timetable and workshop events."""

import logging
from typing import Optional
from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.content import (
    BTN_MASTER_CLASSES,
    CB_MASTER_CLASSES,
    CB_MC_FILTER_ALL,
    CB_MC_FILTER_CHILDREN,
    CB_MC_ITEM_PREFIX,
    MASTER_CLASSES_CHILDREN_EMPTY_MESSAGE,
    MASTER_CLASSES_CHILDREN_MESSAGE,
    MASTER_CLASSES_EMPTY_MESSAGE,
    MASTER_CLASSES_MESSAGE,
)
from bot.masterclasses.keyboards import (
    get_master_class_details_keyboard,
    get_master_classes_inline_keyboard,
)
from bot.sections.base import BaseSection
from bot.timetable.service import TimetableService

logger = logging.getLogger(__name__)


class MasterClasses(BaseSection):
    """Master Classes section delivering workshops and interactive sessions."""

    name = "masterclasses"
    commands = ["masterclasses", "masterclass", "mc", "master_classes"]
    button_text = BTN_MASTER_CLASSES
    callback_data = CB_MASTER_CLASSES
    aliases = {
        "мастер-классы",
        "мастер классы",
        "мастер-класс",
        "мастер класс",
        "мастерклассы",
        "мастеркласс",
        "masterclasses",
        "masterclass",
        "mc",
        "master_classes",
        "/masterclasses",
        "/masterclass",
        "/mc",
        "/master_classes",
        "🎨 мастер-классы",
        "🎨 мастер классы",
    }
    use_reply_keyboard = False

    def __init__(self, service: Optional[TimetableService] = None):
        self.service = service or TimetableService()

    def get_text_content(self, children_only: bool = False) -> str:
        """Return introductory text for master classes section based on active filter."""
        items = self.service.get_master_classes(children_only=children_only)
        if not items:
            return MASTER_CLASSES_CHILDREN_EMPTY_MESSAGE if children_only else MASTER_CLASSES_EMPTY_MESSAGE
        return MASTER_CLASSES_CHILDREN_MESSAGE if children_only else MASTER_CLASSES_MESSAGE

    def get_display_text(self, children_only: bool = False) -> str:
        """Generate formatted overview text with available master classes."""
        items = self.service.get_master_classes(children_only=children_only)
        if not items:
            return self.get_text_content(children_only=children_only)
        lines = [self.get_text_content(children_only=children_only), ""]
        for date_str, _, event in items:
            date_label = self.service.format_date_label(date_str)
            lines.append(f"• {date_label} — {event.title} ({event.time})")
        return "\n".join(lines)

    def get_reply_markup(self, inline: bool = False, children_only: bool = False):
        """Generate inline keyboard for master classes list."""
        items = self.service.get_master_classes(children_only=children_only)
        return get_master_classes_inline_keyboard(
            master_classes=items,
            children_only=children_only,
            date_formatter=self.service.format_date_label,
        )

    def matches_callback(self, callback_data: str) -> bool:
        """Check if callback query belongs to master classes section."""
        return (
            callback_data == self.callback_data
            or callback_data == CB_MC_FILTER_ALL
            or callback_data == CB_MC_FILTER_CHILDREN
            or callback_data.startswith(CB_MC_ITEM_PREFIX)
        )

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle command or direct entry for master classes section."""
        if update.effective_message:
            await self.send_response(
                update.effective_message,
                inline=(not self.use_reply_keyboard),
            )

    async def send_response(self, target: Message, inline: Optional[bool] = None, children_only: bool = False) -> None:
        """Send master classes section entry point."""
        await target.reply_text(
            text=self.get_text_content(children_only=children_only),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_reply_markup(inline=True, children_only=children_only),
        )

    async def handle_callback_query(self, query) -> None:
        """Handle inline button clicks within master classes navigation."""
        data = query.data

        if data == self.callback_data or data == CB_MC_FILTER_ALL:
            await self._show_list(query, children_only=False)
        elif data == CB_MC_FILTER_CHILDREN:
            await self._show_list(query, children_only=True)
        elif data.startswith(CB_MC_ITEM_PREFIX):
            payload = data[len(CB_MC_ITEM_PREFIX):]
            parts = payload.split(":")
            if len(parts) >= 2:
                date_str = parts[0]
                try:
                    idx = int(parts[1])
                except ValueError:
                    await self._show_list(query, children_only=False)
                    return
                children_only = bool(int(parts[2])) if len(parts) > 2 and parts[2].isdigit() else False
                await self._show_details(query, date_str, idx, children_only=children_only)
            else:
                await self._show_list(query, children_only=False)
        else:
            await self._show_list(query, children_only=False)

    async def _show_list(self, query, children_only: bool = False) -> None:
        """Display list of master classes."""
        text = self.get_text_content(children_only=children_only)
        markup = self.get_reply_markup(inline=True, children_only=children_only)
        await self._edit_or_reply(query, text, markup)

    async def _show_details(self, query, date_str: str, event_index: int, children_only: bool = False) -> None:
        """Display details of a specific master class."""
        event = self.service.get_master_class(date_str, event_index)
        if not event:
            await self._show_list(query, children_only=children_only)
            return

        text = self.service.format_master_class_details(date_str, event)
        markup = get_master_class_details_keyboard(children_only=children_only)
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


MasterClassesSection = MasterClasses
