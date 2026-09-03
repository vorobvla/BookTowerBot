"""Wishlist section for managing user book wishlists."""

from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.content import (
    BTN_WISHLIST,
    WISHLIST_ADD_PROMPT,
    WISHLIST_EDIT_PROMPT,
    WISHLIST_EMPTY_MESSAGE,
    WISHLIST_ISBN_PROMPT,
    WISHLIST_MESSAGE,
    WISHLIST_REMOVE_PROMPT,
)
from bot.keyboards import CB_WISHLIST
from bot.sections.base import BaseSection
from bot.wishlist.keyboards import (
    BOOK_ATTRIBUTES,
    CB_WISHLIST_ADD,
    CB_WISHLIST_ADD_ISBN,
    CB_WISHLIST_EDIT,
    CB_WISHLIST_GET,
    CB_WISHLIST_REMOVE,
    CB_WL_CANCEL_ISBN,
    CB_WL_CONFIRM_ISBN,
    CB_WL_EDIT_ATTR_PREFIX,
    CB_WL_EDIT_BOOK_PREFIX,
    CB_WL_REMOVE_BOOK_PREFIX,
    get_book_added_inline_keyboard,
    get_book_attributes_inline_keyboard,
    get_isbn_input_inline_keyboard,
    get_wishlist_add_inline_keyboard,
    get_wishlist_books_inline_keyboard,
    get_wishlist_inline_keyboard,
)
from bot.wishlist.service import WishlistService, get_user_id


class Wishlist(BaseSection):
    """Wishlist section allowing users to store and view their book wishlists."""

    name = "wishlist"
    commands = ["wishlist", "getlist", "addbook", "wishlist_list", "editbook", "removebook", "isbn", "addisbn"]
    button_text = BTN_WISHLIST
    callback_data = CB_WISHLIST
    aliases = {
        "список покупок",
        "список желаемого",
        "wishlist",
        "вишлист",
        "/wishlist",
        "add book",
        "/addbook",
        "добавить книгу",
        "by isbn",
        "/isbn",
        "/addisbn",
        "по isbn",
        "getlist",
        "get list",
        "/getlist",
        "мой список",
        "список книг",
        "edit book",
        "/editbook",
        "редактировать книгу",
        "изменить книгу",
        "remove book",
        "/removebook",
        "удалить книгу",
    }
    use_reply_keyboard = False

    def __init__(self, service: Optional[WishlistService] = None):
        self.service = service or WishlistService()

    def get_text_content(self) -> str:
        return WISHLIST_MESSAGE

    def get_reply_markup(self, inline: bool = False):
        return get_wishlist_inline_keyboard()

    def matches_callback(self, callback_data: str) -> bool:
        """Check whether callback data belongs to the wishlist flow."""
        return (
            callback_data == self.callback_data
            or callback_data == CB_WISHLIST_ADD
            or callback_data == CB_WISHLIST_ADD_ISBN
            or callback_data == CB_WL_CONFIRM_ISBN
            or callback_data == CB_WL_CANCEL_ISBN
            or callback_data == CB_WISHLIST_GET
            or callback_data == CB_WISHLIST_EDIT
            or callback_data == CB_WISHLIST_REMOVE
            or callback_data.startswith(CB_WL_EDIT_BOOK_PREFIX)
            or callback_data.startswith(CB_WL_EDIT_ATTR_PREFIX)
            or callback_data.startswith(CB_WL_REMOVE_BOOK_PREFIX)
        )

    async def send_response(self, target: Message, inline: Optional[bool] = None) -> None:
        """Send wishlist menu with action buttons."""
        await target.reply_text(
            text=self.get_text_content(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_reply_markup(inline=True),
        )

    async def handle_callback_query(self, query, context: Optional[ContextTypes.DEFAULT_TYPE] = None) -> None:
        """Handle interactive inline wishlist callbacks."""
        data = query.data

        # Determine user_id
        telegram_id = None
        if getattr(query, "from_user", None) and getattr(query.from_user, "id", None):
            telegram_id = query.from_user.id
        elif getattr(query, "message", None) and getattr(query.message, "chat", None):
            telegram_id = query.message.chat.id
        else:
            telegram_id = 0
        user_id = get_user_id(telegram_id)

        if data == CB_WISHLIST_ADD:
            if context is not None and hasattr(context, "user_data") and context.user_data is not None:
                context.user_data["awaiting_wishlist_title"] = True
                context.user_data.pop("awaiting_wishlist_isbn", None)
                context.user_data.pop("pending_isbn_book", None)
                context.user_data.pop("awaiting_wishlist_edit", None)
            await self._edit_or_reply(query, WISHLIST_ADD_PROMPT, get_wishlist_add_inline_keyboard())

        elif data == CB_WISHLIST_ADD_ISBN:
            if context is not None and hasattr(context, "user_data") and context.user_data is not None:
                context.user_data["awaiting_wishlist_isbn"] = True
                context.user_data.pop("awaiting_wishlist_title", None)
                context.user_data.pop("pending_isbn_book", None)
                context.user_data.pop("awaiting_wishlist_edit", None)
            await self._edit_or_reply(query, WISHLIST_ISBN_PROMPT, get_isbn_input_inline_keyboard())

        elif data == CB_WL_CONFIRM_ISBN:
            pending_book = None
            if context is not None and hasattr(context, "user_data") and context.user_data is not None:
                pending_book = context.user_data.pop("pending_isbn_book", None)
                context.user_data.pop("awaiting_wishlist_isbn", None)
                context.user_data.pop("awaiting_wishlist_title", None)

            if pending_book:
                added = self.service.add_book(user_id, book=pending_book)
                msg = (
                    f"✅ Книга *«{added.title}»* успешно добавлена в ваш вишлист!\n\n"
                    f"{added.format_entry()}"
                )
                await self._edit_or_reply(query, msg, get_book_added_inline_keyboard(added.id))
            else:
                await self._edit_or_reply(query, WISHLIST_MESSAGE, get_wishlist_inline_keyboard())

        elif data == CB_WL_CANCEL_ISBN:
            if context is not None and hasattr(context, "user_data") and context.user_data is not None:
                context.user_data.pop("pending_isbn_book", None)
                context.user_data.pop("awaiting_wishlist_isbn", None)
                context.user_data.pop("awaiting_wishlist_title", None)
            await self._edit_or_reply(query, "❌ Добавление книги отменено.", get_wishlist_inline_keyboard())

        elif data == CB_WISHLIST_GET:
            text = self.service.format_wishlist_text(user_id)
            await self._edit_or_reply(query, text, get_wishlist_inline_keyboard())

        elif data == CB_WISHLIST_EDIT:
            books = self.service.get_wishlist(user_id)
            if not books:
                await self._edit_or_reply(query, WISHLIST_EMPTY_MESSAGE, get_wishlist_inline_keyboard())
            else:
                markup = get_wishlist_books_inline_keyboard(books, action="edit")
                await self._edit_or_reply(query, WISHLIST_EDIT_PROMPT, markup)

        elif data == CB_WISHLIST_REMOVE:
            books = self.service.get_wishlist(user_id)
            if not books:
                await self._edit_or_reply(query, WISHLIST_EMPTY_MESSAGE, get_wishlist_inline_keyboard())
            else:
                markup = get_wishlist_books_inline_keyboard(books, action="remove")
                await self._edit_or_reply(query, WISHLIST_REMOVE_PROMPT, markup)

        elif data.startswith(CB_WL_EDIT_BOOK_PREFIX):
            book_id_str = data[len(CB_WL_EDIT_BOOK_PREFIX):]
            try:
                book_id = int(book_id_str)
            except ValueError:
                book_id = -1

            book = self.service.get_book(user_id, book_id)
            if not book:
                await self._edit_or_reply(
                    query,
                    "❌ Книга не найдена.",
                    get_wishlist_inline_keyboard(),
                )
            else:
                text = (
                    f"📖 *Редактирование книги:*\n\n"
                    f"{book.format_entry()}\n\n"
                    f"Выберите поле, которое хотите изменить:"
                )
                markup = get_book_attributes_inline_keyboard(book_id)
                await self._edit_or_reply(query, text, markup)

        elif data.startswith(CB_WL_EDIT_ATTR_PREFIX):
            rest = data[len(CB_WL_EDIT_ATTR_PREFIX):]
            try:
                book_id_str, attr_name = rest.split(":", 1)
                book_id = int(book_id_str)
            except ValueError:
                book_id, attr_name = -1, ""

            book = self.service.get_book(user_id, book_id)
            if not book or attr_name not in BOOK_ATTRIBUTES:
                await self._edit_or_reply(
                    query,
                    "❌ Поле или книга не найдены.",
                    get_wishlist_inline_keyboard(),
                )
            else:
                if context is not None and hasattr(context, "user_data") and isinstance(context.user_data, dict):
                    context.user_data["awaiting_wishlist_edit"] = {
                        "book_id": book_id,
                        "attribute": attr_name,
                    }
                    context.user_data.pop("awaiting_wishlist_title", None)

                attr_label = BOOK_ATTRIBUTES.get(attr_name, attr_name)
                curr_val = getattr(book, attr_name, None)
                val_text = f"Текущее значение: *{curr_val}*\n\n" if curr_val is not None else ""
                text = (
                    f"✍️ *Редактирование поля «{attr_label}»*\n"
                    f"Книга: *«{book.title}»*\n\n"
                    f"{val_text}"
                    f"Пожалуйста, введите новое значение сообщением:"
                )
                cancel_markup = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            text="« Отмена",
                            callback_data=f"{CB_WL_EDIT_BOOK_PREFIX}{book_id}",
                        )
                    ]
                ])
                await self._edit_or_reply(query, text, cancel_markup)

        elif data.startswith(CB_WL_REMOVE_BOOK_PREFIX):
            book_id_str = data[len(CB_WL_REMOVE_BOOK_PREFIX):]
            try:
                book_id = int(book_id_str)
            except ValueError:
                book_id = -1

            book = self.service.get_book(user_id, book_id)
            if book:
                title = book.title
                self.service.delete_book(user_id, book_id)
                remaining_books = self.service.get_wishlist(user_id)
                if remaining_books:
                    text = (
                        f"- Книга *«{title}»* удалена из вашего вишлиста.\n\n"
                        f"Выберите следующую книгу для удаления или вернитесь в меню:"
                    )
                    markup = get_wishlist_books_inline_keyboard(remaining_books, action="remove")
                else:
                    text = f"- Книга *«{title}»* удалена из вашего вишлиста.\n\nВаш вишлист теперь пуст."
                    markup = get_wishlist_inline_keyboard()
                await self._edit_or_reply(query, text, markup)
            else:
                await self._edit_or_reply(
                    query,
                    "❌ Книга не найдена или уже удалена.",
                    get_wishlist_inline_keyboard(),
                )

        else:
            markup = self.get_reply_markup(inline=True)
            await self._edit_or_reply(query, self.get_text_content(), markup)

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle Telegram commands for wishlist."""
        telegram_id = (
            update.effective_user.id
            if update.effective_user
            else (update.effective_chat.id if update.effective_chat else 0)
        )
        user_id = get_user_id(telegram_id)

        if update.message and update.message.text:
            cmd = update.message.text.strip().lower()
            if cmd in ["/addbook", "add book", "добавить книгу"]:
                if context is not None and hasattr(context, "user_data") and context.user_data is not None:
                    context.user_data["awaiting_wishlist_title"] = True
                    context.user_data.pop("awaiting_wishlist_isbn", None)
                    context.user_data.pop("pending_isbn_book", None)
                    context.user_data.pop("awaiting_wishlist_edit", None)
                await update.message.reply_text(
                    text=WISHLIST_ADD_PROMPT,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_wishlist_add_inline_keyboard(),
                )
                return
            elif cmd in ["/isbn", "/addisbn", "by isbn", "по isbn", "isbn"]:
                if context is not None and hasattr(context, "user_data") and context.user_data is not None:
                    context.user_data["awaiting_wishlist_isbn"] = True
                    context.user_data.pop("awaiting_wishlist_title", None)
                    context.user_data.pop("pending_isbn_book", None)
                    context.user_data.pop("awaiting_wishlist_edit", None)
                await update.message.reply_text(
                    text=WISHLIST_ISBN_PROMPT,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_isbn_input_inline_keyboard(),
                )
                return
            elif cmd in ["/getlist", "getlist", "get list", "мой список", "/wishlist_list"]:
                text = self.service.format_wishlist_text(user_id)
                await update.message.reply_text(
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.get_reply_markup(inline=True),
                )
                return
            elif cmd in ["/editbook", "edit book", "редактировать книгу", "изменить книгу"]:
                books = self.service.get_wishlist(user_id)
                if not books:
                    await update.message.reply_text(
                        text=WISHLIST_EMPTY_MESSAGE,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=self.get_reply_markup(inline=True),
                    )
                else:
                    await update.message.reply_text(
                        text=WISHLIST_EDIT_PROMPT,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_wishlist_books_inline_keyboard(books, action="edit"),
                    )
                return
            elif cmd in ["/removebook", "remove book", "удалить книгу", "/deletebook"]:
                books = self.service.get_wishlist(user_id)
                if not books:
                    await update.message.reply_text(
                        text=WISHLIST_EMPTY_MESSAGE,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=self.get_reply_markup(inline=True),
                    )
                else:
                    await update.message.reply_text(
                        text=WISHLIST_REMOVE_PROMPT,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_wishlist_books_inline_keyboard(books, action="remove"),
                    )
                return

        if update.effective_message:
            await self.send_response(update.effective_message)

    async def _edit_or_reply(self, query, text: str, markup) -> None:
        """Safely edit query message or send a new reply."""
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


WishlistSection = Wishlist
