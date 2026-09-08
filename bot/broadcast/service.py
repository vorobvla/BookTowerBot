"""Broadcast service executing announcements and command dispatches to registered chats."""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
from telegram.constants import ParseMode

from bot.broadcast.registry import ChatRegistry, default_chat_registry
from bot.content import (
    CB_CHILDREN_ACTIVITY,
    CB_HELP,
    CB_MAP,
    CB_MASTER_CLASSES,
    CB_PARTICIPANTS,
    CB_RECOMMENDATIONS,
    CB_TIMETABLE,
    CB_WISHLIST,
    CB_WISHLIST_GET,
    MAP_UNAVAILABLE_MESSAGE,
)
from bot.sections.registry import SectionRegistry, default_registry
from bot.wishlist.service import WishlistService, get_user_id

logger = logging.getLogger(__name__)

# List of supported broadcast commands with human-readable labels
AVAILABLE_BROADCAST_COMMANDS = [
    {
        "command": "start",
        "title": "🏁 Главное меню (/start)",
        "description": "Приветственное сообщение и кнопки основных разделов",
    },
    {
        "command": "map",
        "title": "🏢 Карта площадки (/map)",
        "description": "Карта ярмарки и интерактивная сетка стендов",
    },
    {
        "command": "timetables",
        "title": "📅 Расписание (/timetables)",
        "description": "Расписание фестиваля с кнопками выбора дат",
    },
    {
        "command": "children",
        "title": "🎈 Детская программа (/children)",
        "description": "Детская программа мероприятий с кнопками дат",
    },
    {
        "command": "masterclasses",
        "title": "🎨 Мастер-классы (/masterclasses)",
        "description": "Список мастер-классов фестиваля с кнопками",
    },
    {
        "command": "recommendations",
        "title": "📚 Рекомендации (/recommendations)",
        "description": "Подборки книг и рекомендуемые стенды",
    },
    {
        "command": "participants",
        "title": "👥 Участники (/participants)",
        "description": "Список участников и информация о стендах",
    },
    {
        "command": "wishlist",
        "title": "📝 Меню вишлиста (/wishlist)",
        "description": "Главное меню работы с вишлистом",
    },
    {
        "command": "wishlist_get",
        "title": "📋 Вишлист пользователя (текст)",
        "description": "Персональный список сохраненных книг для пользователя",
    },
    {
        "command": "help",
        "title": "ℹ️ Справка (/help)",
        "description": "Справочное сообщение со списком всех команд",
    },
]


class BroadcastService:
    """Service handling text announcements and command executions across all registered Telegram chats."""

    def __init__(
        self,
        bot: Any = None,
        registry: Optional[ChatRegistry] = None,
        section_registry: Optional[SectionRegistry] = None,
        wishlist_service: Optional[WishlistService] = None,
        rate_limit_delay: float = 0.03,
    ) -> None:
        self.bot = bot
        self.registry = registry or default_chat_registry
        self.section_registry = section_registry or default_registry
        self.wishlist_service = wishlist_service or WishlistService()
        self.rate_limit_delay = rate_limit_delay

    @staticmethod
    def get_available_commands() -> List[Dict[str, str]]:
        """Return the catalog of commands available for broadcast."""
        return AVAILABLE_BROADCAST_COMMANDS

    def _normalize_command(self, command: str) -> str:
        """Normalize command string by removing leading slashes and whitespace."""
        return command.strip().lstrip("/").lower()

    def _is_wishlist_get_command(self, cmd_normalized: str) -> bool:
        """Check if command corresponds to personal wishlist text dispatch."""
        return cmd_normalized in {
            "wishlist_get",
            "getlist",
            "get_list",
            "get_wishlist",
            "my_wishlist",
            "wl_get",
            CB_WISHLIST_GET.lower(),
        }

    async def broadcast_message(
        self,
        text: str,
        parse_mode: str = "Markdown",
        chat_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Broadcast custom text message to all registered chats."""
        if not text or not text.strip():
            return {
                "status": "error",
                "message": "Message text is empty",
                "total_chats": 0,
                "sent_count": 0,
                "failed_count": 0,
                "errors": [],
            }

        chats = chat_ids if chat_ids is not None else self.registry.get_all()
        total_chats = len(chats)
        sent_count = 0
        failed_count = 0
        errors: List[Dict[str, Any]] = []

        pm = ParseMode.MARKDOWN if parse_mode.lower() in ("markdown", "md") else None

        for chat_id in chats:
            try:
                if self.bot is not None:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=text.strip(),
                        parse_mode=pm,
                    )
                sent_count += 1
                if self.rate_limit_delay > 0:
                    await asyncio.sleep(self.rate_limit_delay)
            except Exception as e:
                logger.warning("Broadcast message failed for chat_id %d: %s", chat_id, e)
                failed_count += 1
                errors.append({"chat_id": chat_id, "error": str(e)})

        return {
            "status": "ok",
            "total_chats": total_chats,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "errors": errors,
        }

    async def _send_section_to_chat(self, chat_id: int, section: Any) -> None:
        """Send a resolved section's message or photo + markup to a specific chat."""
        from bot.sections.map import Map

        # Handle Map section which may send photo
        if isinstance(section, Map):
            image_path = getattr(section, "image_path", None)
            markup = section.get_reply_markup(inline=True)
            caption = section.get_text_content()

            if image_path and os.path.exists(image_path):
                cached_id = getattr(section, "cached_file_id", None)
                if cached_id:
                    try:
                        await self.bot.send_photo(
                            chat_id=chat_id,
                            photo=cached_id,
                            caption=caption if caption else None,
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=markup,
                        )
                        return
                    except Exception as e:
                        logger.warning("Failed sending map with cached_file_id: %s. Falling back to disk upload.", e)

                with open(image_path, "rb") as photo_file:
                    sent_msg = await self.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo_file,
                        caption=caption if caption else None,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=markup,
                    )
                    if sent_msg and getattr(sent_msg, "photo", None):
                        section.cached_file_id = sent_msg.photo[-1].file_id
                return
            else:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=MAP_UNAVAILABLE_MESSAGE,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=markup,
                )
                return

        # Default section sending
        text = section.get_text_content()
        markup = section.get_reply_markup(inline=True)
        await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup,
        )

    async def broadcast_command(
        self,
        command: str,
        chat_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Broadcast command output to all registered chats."""
        if not command or not command.strip():
            return {
                "status": "error",
                "message": "Command is empty",
                "total_chats": 0,
                "sent_count": 0,
                "failed_count": 0,
                "errors": [],
            }

        cmd_norm = self._normalize_command(command)
        chats = chat_ids if chat_ids is not None else self.registry.get_all()
        total_chats = len(chats)
        sent_count = 0
        failed_count = 0
        errors: List[Dict[str, Any]] = []

        is_wishlist_get = self._is_wishlist_get_command(cmd_norm)
        section = None

        if not is_wishlist_get:
            section = self.section_registry.find_by_command(cmd_norm) or self.section_registry.find_by_callback(cmd_norm)
            if not section:
                # Try finding by callback aliases
                alias_callbacks = {
                    "start": "start",
                    "map": CB_MAP,
                    "timetables": CB_TIMETABLE,
                    "timetable": CB_TIMETABLE,
                    "children": CB_CHILDREN_ACTIVITY,
                    "masterclasses": CB_MASTER_CLASSES,
                    "mc": CB_MASTER_CLASSES,
                    "recommendations": CB_RECOMMENDATIONS,
                    "recs": CB_RECOMMENDATIONS,
                    "participants": CB_PARTICIPANTS,
                    "wishlist": CB_WISHLIST,
                    "help": CB_HELP,
                }
                cb_target = alias_callbacks.get(cmd_norm)
                if cb_target:
                    section = self.section_registry.find_by_callback(cb_target)

            if not section:
                return {
                    "status": "error",
                    "message": f"Unsupported or unknown command: {command}",
                    "total_chats": total_chats,
                    "sent_count": 0,
                    "failed_count": 0,
                    "errors": [{"error": f"Unknown command: {command}"}],
                }

        for chat_id in chats:
            try:
                if self.bot is not None:
                    if is_wishlist_get:
                        user_id = get_user_id(chat_id)
                        wishlist_text = self.wishlist_service.format_wishlist_text(user_id)
                        await self.bot.send_message(
                            chat_id=chat_id,
                            text=wishlist_text,
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    else:
                        await self._send_section_to_chat(chat_id, section)
                sent_count += 1
                if self.rate_limit_delay > 0:
                    await asyncio.sleep(self.rate_limit_delay)
            except Exception as e:
                logger.warning("Broadcast command '%s' failed for chat_id %d: %s", command, chat_id, e)
                failed_count += 1
                errors.append({"chat_id": chat_id, "error": str(e)})

        return {
            "status": "ok",
            "total_chats": total_chats,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "errors": errors,
        }

    async def broadcast(
        self,
        text: Optional[str] = None,
        command: Optional[str] = None,
        parse_mode: str = "Markdown",
        chat_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Perform composite broadcast: custom text message, command execution, or both."""
        has_text = bool(text and text.strip())
        has_command = bool(command and command.strip())

        if not has_text and not has_command:
            return {
                "status": "error",
                "message": "Both text and command are empty. Please specify a message, a command, or both.",
                "total_chats": 0,
                "sent_count": 0,
                "failed_count": 0,
                "errors": [],
            }

        chats = chat_ids if chat_ids is not None else self.registry.get_all()
        total_chats = len(chats)

        if has_text and not has_command:
            return await self.broadcast_message(text=text.strip(), parse_mode=parse_mode, chat_ids=chats)

        if has_command and not has_text:
            return await self.broadcast_command(command=command.strip(), chat_ids=chats)

        # Composite broadcast: send text first, then command
        sent_count = 0
        failed_count = 0
        errors: List[Dict[str, Any]] = []

        # Validate command first before dispatching
        cmd_norm = self._normalize_command(command)
        is_wishlist_get = self._is_wishlist_get_command(cmd_norm)
        section = None
        if not is_wishlist_get:
            section = self.section_registry.find_by_command(cmd_norm) or self.section_registry.find_by_callback(cmd_norm)
            if not section:
                alias_callbacks = {
                    "start": "start",
                    "map": CB_MAP,
                    "timetables": CB_TIMETABLE,
                    "timetable": CB_TIMETABLE,
                    "children": CB_CHILDREN_ACTIVITY,
                    "masterclasses": CB_MASTER_CLASSES,
                    "mc": CB_MASTER_CLASSES,
                    "recommendations": CB_RECOMMENDATIONS,
                    "recs": CB_RECOMMENDATIONS,
                    "participants": CB_PARTICIPANTS,
                    "wishlist": CB_WISHLIST,
                    "help": CB_HELP,
                }
                cb_target = alias_callbacks.get(cmd_norm)
                if cb_target:
                    section = self.section_registry.find_by_callback(cb_target)

            if not section:
                return {
                    "status": "error",
                    "message": f"Unsupported or unknown command: {command}",
                    "total_chats": total_chats,
                    "sent_count": 0,
                    "failed_count": 0,
                    "errors": [{"error": f"Unknown command: {command}"}],
                }

        pm = ParseMode.MARKDOWN if parse_mode.lower() in ("markdown", "md") else None

        for chat_id in chats:
            chat_failed = False
            # 1. Send custom text message
            try:
                if self.bot is not None:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=text.strip(),
                        parse_mode=pm,
                    )
            except Exception as e:
                logger.warning("Composite broadcast message part failed for chat_id %d: %s", chat_id, e)
                chat_failed = True
                errors.append({"chat_id": chat_id, "step": "message", "error": str(e)})

            # 2. Send command output
            try:
                if self.bot is not None:
                    if is_wishlist_get:
                        user_id = get_user_id(chat_id)
                        wishlist_text = self.wishlist_service.format_wishlist_text(user_id)
                        await self.bot.send_message(
                            chat_id=chat_id,
                            text=wishlist_text,
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    else:
                        await self._send_section_to_chat(chat_id, section)
            except Exception as e:
                logger.warning("Composite broadcast command part failed for chat_id %d: %s", chat_id, e)
                chat_failed = True
                errors.append({"chat_id": chat_id, "step": "command", "error": str(e)})

            if chat_failed:
                failed_count += 1
            else:
                sent_count += 1

            if self.rate_limit_delay > 0:
                await asyncio.sleep(self.rate_limit_delay)

        return {
            "status": "ok",
            "total_chats": total_chats,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "errors": errors,
        }
