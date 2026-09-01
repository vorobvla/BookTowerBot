"""Help section for bot guidance and /help command."""

from bot.content import BTN_HELP, HELP_MESSAGE
from bot.keyboards import CB_HELP
from bot.sections.base import BaseSection


class Help(BaseSection):
    """Help section handling /help command, button, and callbacks."""

    name = "help"
    commands = ["help"]
    button_text = BTN_HELP
    callback_data = CB_HELP
    aliases = {"помощь", "справка", "help", "info", "/help"}
    use_reply_keyboard = True

    def get_text_content(self) -> str:
        return HELP_MESSAGE


HelpSection = Help
