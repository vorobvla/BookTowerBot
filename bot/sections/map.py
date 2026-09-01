"""Map section for venue layout and map image."""

import os
from typing import Optional
from telegram import Message
from telegram.constants import ParseMode

from bot.content import BTN_MAP, MAP_MESSAGE, MAP_PATH
from bot.keyboards import CB_MAP
from bot.sections.base import BaseSection


class Map(BaseSection):
    """Map section handling venue map image and layout descriptions."""

    name = "map"
    commands = ["map"]
    button_text = BTN_MAP
    callback_data = CB_MAP
    aliases = {"карта", "план", "схема", "map", "venue map", "venue", "/map"}
    use_reply_keyboard = False

    def __init__(self, image_path: Optional[str] = None):
        self.image_path = image_path or MAP_PATH

    def get_text_content(self) -> str:
        return MAP_MESSAGE

    def get_display_text(self) -> str:
        return f"[Image: {self.image_path}]\n{self.get_text_content()}"

    async def send_response(self, target: Message, inline: Optional[bool] = None) -> None:
        """Send map image with caption and markup."""
        use_inline = not self.use_reply_keyboard if inline is None else inline
        markup = self.get_reply_markup(inline=use_inline)

        if os.path.exists(self.image_path):
            with open(self.image_path, "rb") as photo:
                await target.reply_photo(
                    photo=photo,
                    caption=self.get_text_content(),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=markup,
                )
        else:
            await target.reply_photo(
                photo=self.image_path,
                caption=self.get_text_content(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=markup,
            )


MapSection = Map
