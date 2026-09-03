"""Participants section for displaying participants list and individual stand info."""

from typing import Optional
from telegram import Message
from telegram.constants import ParseMode

from bot.content import BTN_PARTICIPANTS, PARTICIPANTS_MESSAGE
from bot.keyboards import CB_PARTICIPANTS
from bot.participants.keyboards import (
    CB_PART_ITEM_PREFIX,
    CB_PARTICIPANTS_LIST,
    get_participant_details_keyboard,
    get_participants_inline_keyboard,
)
from bot.participants.service import ParticipantsService
from bot.sections.base import BaseSection


class Participants(BaseSection):
    """Participants section handling participant listing and stand details."""

    name = "participants"
    commands = ["participants", "stands", "vendors", "part"]
    button_text = BTN_PARTICIPANTS
    callback_data = CB_PARTICIPANTS
    aliases = {
        "участники",
        "участник",
        "стенды",
        "стенд",
        "participants",
        "stands",
        "vendors",
        "part",
        "/participants",
        "/stands",
        "/vendors",
        "/part",
    }
    use_reply_keyboard = False

    def __init__(self, service: Optional[ParticipantsService] = None):
        self.service = service or ParticipantsService()

    def get_text_content(self) -> str:
        return PARTICIPANTS_MESSAGE

    def get_display_text(self) -> str:
        participants = self.service.get_participants()
        if not participants:
            return self.get_text_content()
        formatted = [f"• {p.format_button_label()}" for p in participants]
        return f"{self.get_text_content()}\n\n" + "\n".join(formatted)

    def get_reply_markup(self, inline: bool = False):
        participants = self.service.get_participants()
        return get_participants_inline_keyboard(participants=participants)

    def matches_callback(self, callback_data: str) -> bool:
        """Check whether callback data belongs to the participants flow."""
        return (
            callback_data == self.callback_data
            or callback_data == CB_PARTICIPANTS_LIST
            or callback_data.startswith(CB_PART_ITEM_PREFIX)
        )

    async def send_response(self, target: Message, inline: Optional[bool] = None) -> None:
        """Send participants initial response with participant selection buttons."""
        await target.reply_text(
            text=self.get_text_content(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_reply_markup(inline=True),
        )

    async def handle_callback_query(self, query) -> None:
        """Handle interactive inline participants callbacks."""
        data = query.data

        if data == self.callback_data or data == CB_PARTICIPANTS_LIST:
            await self._show_participants(query)
        elif data.startswith(CB_PART_ITEM_PREFIX):
            item_payload = data[len(CB_PART_ITEM_PREFIX):]
            if ":s:" in item_payload:
                item_id, stand_key = item_payload.split(":s:", 1)
            elif ":stand:" in item_payload:
                item_id, stand_key = item_payload.split(":stand:", 1)
            else:
                item_id, stand_key = item_payload, None
            await self._show_participant_details(query, item_id, stand_key=stand_key)
        else:
            await self._show_participants(query)

    async def _show_participants(self, query) -> None:
        markup = self.get_reply_markup(inline=True)
        await self._edit_or_reply(query, self.get_text_content(), markup)

    async def _show_participant_details(
        self,
        query,
        item_id: str,
        stand_key: Optional[str] = None,
    ) -> None:
        text = self.service.format_participant_details(item_id)
        markup = get_participant_details_keyboard(stand_key=stand_key)
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


ParticipantsSection = Participants
