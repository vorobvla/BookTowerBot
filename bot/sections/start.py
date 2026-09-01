"""Start section for bot greeting and /start command."""

from bot.content import START_MESSAGE
from bot.sections.base import BaseSection


class Start(BaseSection):
    """Start section handling /start command and bot greeting."""

    name = "start"
    commands = ["start"]
    aliases = {"start", "/start"}
    use_reply_keyboard = True

    def get_text_content(self) -> str:
        return START_MESSAGE


StartSection = Start
