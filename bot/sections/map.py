"""Map section for venue layout and map image."""

import logging
import os
from typing import Optional
from telegram import Message
from telegram.constants import ParseMode

from bot.content import BTN_MAP, MAP_MESSAGE, MAP_PATH
from bot.keyboards import CB_MAP
from bot.sections.base import BaseSection

logger = logging.getLogger(__name__)


class Map(BaseSection):
    """Map section handling venue map image and layout descriptions."""

    name = "map"
    commands = ["map"]
    button_text = BTN_MAP
    callback_data = CB_MAP
    aliases = {"карта", "план", "схема", "map", "venue map", "venue", "/map"}
    use_reply_keyboard = False

    _global_cached_file_id: Optional[str] = None

    def __init__(
        self,
        image_path: Optional[str] = None,
        cached_file_id: Optional[str] = None,
    ):
        self.image_path = image_path or MAP_PATH
        self._cached_file_id = cached_file_id

    @property
    def cached_file_id(self) -> Optional[str]:
        if self._cached_file_id is not None:
            return self._cached_file_id
        if self.image_path == MAP_PATH:
            return Map._global_cached_file_id
        return None

    @cached_file_id.setter
    def cached_file_id(self, value: Optional[str]) -> None:
        self._cached_file_id = value
        if self.image_path == MAP_PATH:
            Map._global_cached_file_id = value

    def get_text_content(self) -> str:
        return MAP_MESSAGE

    def get_display_text(self) -> str:
        return f"[Image: {self.image_path}]\n{self.get_text_content()}"

    async def send_response(self, target: Message, inline: Optional[bool] = None) -> None:
        """Send map image with caption and markup, using cached file_id when available."""
        use_inline = not self.use_reply_keyboard if inline is None else inline
        markup = self.get_reply_markup(inline=use_inline)

        if self.cached_file_id:
            try:
                await target.reply_photo(
                    photo=self.cached_file_id,
                    caption=self.get_text_content(),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=markup,
                )
                return
            except Exception as e:
                logger.warning("Failed to send map using cached file_id: %s. Falling back to upload.", e)
                self.cached_file_id = None

        sent_message = None
        if os.path.exists(self.image_path):
            with open(self.image_path, "rb") as photo:
                sent_message = await target.reply_photo(
                    photo=photo,
                    caption=self.get_text_content(),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=markup,
                )
        else:
            sent_message = await target.reply_photo(
                photo=self.image_path,
                caption=self.get_text_content(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=markup,
            )

        if sent_message and hasattr(sent_message, "photo"):
            photos = getattr(sent_message, "photo", None)
            if isinstance(photos, (list, tuple)) and photos:
                last_photo = photos[-1]
                file_id = getattr(last_photo, "file_id", None)
                if file_id and isinstance(file_id, str):
                    self.cached_file_id = file_id


MapSection = Map
