"""Abstract base class for bot sections."""

from abc import ABC, abstractmethod
from typing import List, Optional, Set
from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.keyboards import (
    get_main_inline_keyboard,
    get_main_reply_keyboard,
)


class BaseSection(ABC):
    """Abstract base class representing a bot section or feature."""

    name: str = ""
    commands: List[str] = []
    button_text: Optional[str] = None
    callback_data: Optional[str] = None
    aliases: Set[str] = set()
    use_reply_keyboard: bool = False

    @abstractmethod
    def get_text_content(self) -> str:
        """Return text/markdown content for this section."""
        pass

    def get_display_text(self) -> str:
        """Return formatted text representation for CLI/display."""
        return self.get_text_content()

    def get_reply_markup(self, inline: bool = False):
        """Return appropriate keyboard markup based on context."""
        if inline or not self.use_reply_keyboard:
            return get_main_inline_keyboard()
        return get_main_reply_keyboard()

    def matches_text(self, text: str) -> bool:
        """Check whether input text matches button, alias, or command."""
        cleaned = text.strip()
        normalized = cleaned.lower()

        if self.button_text and cleaned == self.button_text:
            return True
        if normalized in self.aliases:
            return True
        for cmd in self.commands:
            if normalized == f"/{cmd}" or normalized == cmd:
                return True
        return False

    def matches_callback(self, callback_data: str) -> bool:
        """Check whether callback data matches this section."""
        return bool(self.callback_data and self.callback_data == callback_data)

    def matches_command(self, command: str) -> bool:
        """Check whether command matches this section."""
        cmd = command.lstrip("/").lower()
        return cmd in self.commands

    async def send_response(self, target: Message, inline: Optional[bool] = None) -> None:
        """Send response message to a target Telegram message object."""
        use_inline = not self.use_reply_keyboard if inline is None else inline
        await target.reply_text(
            text=self.get_text_content(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_reply_markup(inline=use_inline),
        )

    async def handle_callback_query(self, query) -> None:
        """Handle callback query for this section."""
        if getattr(query, "message", None):
            await self.send_response(query.message, inline=True)

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle Telegram update for this section."""
        if update.effective_message:
            await self.send_response(update.effective_message)
