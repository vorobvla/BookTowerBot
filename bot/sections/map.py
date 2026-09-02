"""Map section for venue layout and map image."""

import json
import logging
import os
from typing import Optional
from telegram import Message
from telegram.constants import ParseMode

from bot.content import BTN_MAP, MAP_DIR, MAP_MESSAGE, MAP_PATH, MAP_UNAVAILABLE_MESSAGE
from bot.keyboards import CB_MAP
from bot.sections.base import BaseSection

logger = logging.getLogger(__name__)


def get_current_map_path() -> Optional[str]:
    """Retrieve the currently active map path from assets/map directory if it exists."""
    meta_file = os.path.join(MAP_DIR, "active_map.json")
    if os.path.exists(meta_file):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                active_name = data.get("active_map")
                if active_name and isinstance(active_name, str):
                    target_path = os.path.join(MAP_DIR, active_name)
                    if os.path.exists(target_path) and os.path.isfile(target_path):
                        return target_path
        except Exception:
            pass

    txt_file = os.path.join(MAP_DIR, "active_map.txt")
    if os.path.exists(txt_file):
        try:
            with open(txt_file, "r", encoding="utf-8") as f:
                active_name = f.read().strip()
                if active_name:
                    target_path = os.path.join(MAP_DIR, active_name)
                    if os.path.exists(target_path) and os.path.isfile(target_path):
                        return target_path
        except Exception:
            pass

    map_png = os.path.join(MAP_DIR, "map.png")
    if os.path.exists(map_png) and os.path.isfile(map_png):
        return map_png

    if os.path.exists(MAP_PATH) and os.path.isfile(MAP_PATH):
        return MAP_PATH

    # Check if any supported image file exists in MAP_DIR
    if os.path.exists(MAP_DIR) and os.path.isdir(MAP_DIR):
        try:
            for fname in sorted(os.listdir(MAP_DIR)):
                ext = os.path.splitext(fname)[1].lower()
                if ext in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"} and not fname.startswith("."):
                    candidate = os.path.join(MAP_DIR, fname)
                    if os.path.isfile(candidate):
                        return candidate
        except Exception:
            pass

    return None


class Map(BaseSection):
    """Map section handling venue map image and layout descriptions."""

    name = "map"
    commands = ["map"]
    button_text = BTN_MAP
    callback_data = CB_MAP
    aliases = {"карта", "план", "схема", "map", "venue map", "venue", "/map"}
    use_reply_keyboard = False

    _global_cached_file_id: Optional[str] = None
    _global_cached_image_path: Optional[str] = None
    _global_cached_mtime: Optional[float] = None

    def __init__(
        self,
        image_path: Optional[str] = None,
        cached_file_id: Optional[str] = None,
    ):
        self._custom_image_path: Optional[str] = image_path
        self._cached_file_id: Optional[str] = cached_file_id
        self._cached_image_path: Optional[str] = image_path if cached_file_id else None
        self._cached_mtime: Optional[float] = None

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all in-memory map caches."""
        cls._global_cached_file_id = None
        cls._global_cached_image_path = None
        cls._global_cached_mtime = None

    @property
    def image_path(self) -> Optional[str]:
        """Dynamically return the active image path if none was explicitly configured."""
        if self._custom_image_path is not None:
            return self._custom_image_path
        return get_current_map_path()

    @image_path.setter
    def image_path(self, value: Optional[str]) -> None:
        self._custom_image_path = value

    def _get_path_mtime(self, path: Optional[str]) -> float:
        if not path:
            return 0.0
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0.0

    @property
    def cached_file_id(self) -> Optional[str]:
        """Retrieve cached Telegram file_id if valid for the current map file."""
        current_path = self.image_path
        if not current_path:
            return None

        current_mtime = self._get_path_mtime(current_path)

        # Check instance-level cache
        if self._cached_file_id is not None:
            if self._cached_image_path is None or (
                self._cached_image_path == current_path
                and (self._cached_mtime is None or current_mtime == 0.0 or self._cached_mtime == current_mtime)
            ):
                return self._cached_file_id
            self._cached_file_id = None
            self._cached_image_path = None
            self._cached_mtime = None

        # Check global cache
        if (
            Map._global_cached_image_path == current_path
            and Map._global_cached_file_id is not None
        ):
            if (
                Map._global_cached_mtime is None
                or current_mtime == 0.0
                or Map._global_cached_mtime == current_mtime
            ):
                return Map._global_cached_file_id

        return None

    @cached_file_id.setter
    def cached_file_id(self, value: Optional[str]) -> None:
        current_path = self.image_path
        self._cached_file_id = value
        mtime = self._get_path_mtime(current_path) if (current_path and os.path.exists(current_path)) else 0.0

        self._cached_image_path = current_path if value else None
        self._cached_mtime = mtime if value else None

        if value is not None and current_path is not None:
            Map._global_cached_file_id = value
            Map._global_cached_image_path = current_path
            Map._global_cached_mtime = mtime
        else:
            Map._global_cached_file_id = None
            Map._global_cached_image_path = None
            Map._global_cached_mtime = None

    def get_text_content(self) -> str:
        return MAP_MESSAGE

    def get_display_text(self) -> str:
        current_path = self.image_path
        if current_path:
            caption = self.get_text_content()
            return f"[Image: {current_path}]\n{caption}" if caption else f"[Image: {current_path}]"
        return MAP_UNAVAILABLE_MESSAGE

    async def send_response(self, target: Message, inline: Optional[bool] = None) -> None:
        """Send map image with caption and markup, using cached file_id when available, or placeholder if missing."""
        use_inline = not self.use_reply_keyboard if inline is None else inline
        markup = self.get_reply_markup(inline=use_inline)

        current_path = self.image_path

        # If no map file exists at all on disk, reply with placeholder text message
        if not current_path or not os.path.exists(current_path):
            logger.info("No venue map available on disk. Sending placeholder message.")
            await target.reply_text(
                text=MAP_UNAVAILABLE_MESSAGE,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=markup,
            )
            return

        # 1. Try sending via cached Telegram file_id
        cached_id = self.cached_file_id
        if cached_id:
            try:
                await target.reply_photo(
                    photo=cached_id,
                    caption=self.get_text_content(),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=markup,
                )
                return
            except Exception as e:
                logger.warning(
                    "Failed to send map using cached file_id %s: %s. Clearing cache and retrying upload.",
                    cached_id,
                    e,
                )
                self.cached_file_id = None
                Map.clear_cache()

        # 2. Upload photo from disk
        sent_message = None
        try:
            with open(current_path, "rb") as photo_file:
                sent_message = await target.reply_photo(
                    photo=photo_file,
                    caption=self.get_text_content(),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=markup,
                )
        except Exception as e:
            logger.error("Failed to upload venue map photo '%s': %s", current_path, e)
            await target.reply_text(
                text=MAP_UNAVAILABLE_MESSAGE,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=markup,
            )
            return

        # 3. Store new file_id in cache for subsequent requests
        if sent_message and hasattr(sent_message, "photo"):
            photos = getattr(sent_message, "photo", None)
            if isinstance(photos, (list, tuple)) and photos:
                last_photo = photos[-1]
                file_id = getattr(last_photo, "file_id", None)
                if file_id and isinstance(file_id, str):
                    self.cached_file_id = file_id


MapSection = Map
