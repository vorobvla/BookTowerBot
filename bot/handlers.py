"""Telegram bot command, message, and callback handlers."""

import inspect
import logging
import os
import tempfile
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.content import (
    UNKNOWN_COMMAND_MESSAGE,
    WISHLIST_ADD_PROMPT,
    WISHLIST_BARCODE_NOT_FOUND_MESSAGE,
    WISHLIST_EDIT_PROMPT,
    WISHLIST_EMPTY_MESSAGE,
    WISHLIST_ISBN_INVALID_MESSAGE,
    WISHLIST_ISBN_NOT_FOUND_MESSAGE,
    WISHLIST_ISBN_PROMPT,
    WISHLIST_REMOVE_PROMPT,
)
from bot.keyboards import get_main_reply_keyboard
from bot.sections import (
    ChildrenActivity,
    Help,
    Map,
    Participants,
    Recommendations,
    Start,
    Timetable,
    Wishlist,
    default_registry,
)
from bot.wishlist.isbn import clean_isbn, decode_barcode_from_image, lookup_book_by_isbn
from bot.wishlist.keyboards import (
    BOOK_ATTRIBUTES,
    get_book_attributes_inline_keyboard,
    get_isbn_confirm_inline_keyboard,
    get_isbn_input_inline_keyboard,
    get_wishlist_add_inline_keyboard,
    get_wishlist_books_inline_keyboard,
)
from bot.wishlist.service import get_user_id

logger = logging.getLogger(__name__)

# Section singletons
start_section = Start()
help_section = Help()
map_section = Map()
timetable_section = Timetable()
children_activity_section = ChildrenActivity()
recommendations_section = Recommendations()
participants_section = Participants()
wishlist_section = Wishlist()


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await start_section.handle(update, context)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await help_section.handle(update, context)


async def map_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /map command."""
    await map_section.handle(update, context)


async def timetable_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /timetables command."""
    await timetable_section.handle(update, context)


async def children_activity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /children and /children_activity commands."""
    await children_activity_section.handle(update, context)


async def recommendations_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /recommendations and /recs commands."""
    await recommendations_section.handle(update, context)


async def participants_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /participants, /stands, and /vendors commands."""
    await participants_section.handle(update, context)


async def wishlist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /wishlist, /getlist, and /addbook commands."""
    await wishlist_section.handle(update, context)


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callback queries."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    section = default_registry.find_by_callback(query.data)
    if section:
        if hasattr(section, "handle_callback_query"):
            sig = inspect.signature(section.handle_callback_query)
            if "context" in sig.parameters or len(sig.parameters) >= 2:
                await section.handle_callback_query(query, context=context)
            else:
                await section.handle_callback_query(query)
        elif query.message:
            await section.send_response(query.message, inline=True)


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages matching reply keyboard buttons or custom input."""
    if not update.effective_message or not update.effective_message.text:
        return

    text = update.effective_message.text.strip()
    telegram_id = (
        update.effective_user.id
        if update.effective_user
        else (update.effective_chat.id if update.effective_chat else 0)
    )
    user_id = get_user_id(telegram_id)

    # Check if we are awaiting a wishlist book edit
    edit_info = None
    if context is not None and hasattr(context, "user_data") and isinstance(context.user_data, dict):
        edit_info = context.user_data.get("awaiting_wishlist_edit")

    if edit_info and isinstance(edit_info, dict):
        if text.startswith("/"):
            context.user_data.pop("awaiting_wishlist_edit", None)
        else:
            book_id = edit_info.get("book_id")
            attribute = edit_info.get("attribute")
            context.user_data.pop("awaiting_wishlist_edit", None)

            fallback_markup = (
                get_book_attributes_inline_keyboard(book_id)
                if book_id is not None
                else wishlist_section.get_reply_markup(inline=True)
            )

            if attribute == "title" and not text:
                await update.effective_message.reply_text(
                    text="❌ Название книги не может быть пустым.",
                    reply_markup=fallback_markup,
                )
                return

            value = text
            if attribute == "year":
                try:
                    value = int(value)
                except ValueError:
                    await update.effective_message.reply_text(
                        text="❌ Год издания должен быть числом (например, 2024).",
                        reply_markup=fallback_markup,
                    )
                    return

            try:
                updated_book = wishlist_section.service.update_book_attribute(user_id, book_id, attribute, value)
            except Exception as e:
                logger.error(f"Error updating book attribute: {e}")
                updated_book = None

            if updated_book:
                attr_label = BOOK_ATTRIBUTES.get(attribute, attribute)
                await update.effective_message.reply_text(
                    text=f"✅ Поле *«{attr_label}»* для книги *«{updated_book.title}»* успешно обновлено!\n\n{updated_book.format_entry()}",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_book_attributes_inline_keyboard(book_id),
                )
            else:
                await update.effective_message.reply_text(
                    text="❌ Не удалось обновить книгу (возможно, она была удалена).",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=wishlist_section.get_reply_markup(inline=True),
                )
            return

    # Check if we are awaiting a wishlist book ISBN
    is_awaiting_isbn = False
    if context is not None and hasattr(context, "user_data") and isinstance(context.user_data, dict):
        is_awaiting_isbn = bool(context.user_data.get("awaiting_wishlist_isbn"))

    if is_awaiting_isbn:
        if text.startswith("/"):
            context.user_data["awaiting_wishlist_isbn"] = False
        else:
            cleaned_isbn = clean_isbn(text)
            if cleaned_isbn:
                book = lookup_book_by_isbn(cleaned_isbn)
                if book:
                    context.user_data["pending_isbn_book"] = book
                    context.user_data.pop("awaiting_wishlist_isbn", None)
                    context.user_data.pop("awaiting_wishlist_title", None)
                    await update.effective_message.reply_text(
                        text=f"📖 *Найдена книга:*\n\n{book.format_entry()}\n\nДобавить эту книгу в ваш вишлист?",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_isbn_confirm_inline_keyboard(),
                    )
                    return
                else:
                    context.user_data.pop("awaiting_wishlist_isbn", None)
                    context.user_data["awaiting_wishlist_title"] = True
                    await update.effective_message.reply_text(
                        text=f"❌ *Книга по указанному ISBN ({cleaned_isbn}) не найдена.*\n\nВы можете попробовать еще раз или отправить название книги сообщением для добавления вручную:",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_wishlist_add_inline_keyboard(),
                    )
                    return
            else:
                await update.effective_message.reply_text(
                    text=WISHLIST_ISBN_INVALID_MESSAGE,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_isbn_input_inline_keyboard(),
                )
                return

    # Check if we are awaiting a wishlist book title
    is_awaiting_title = False
    if context is not None and hasattr(context, "user_data") and isinstance(context.user_data, dict):
        is_awaiting_title = bool(context.user_data.get("awaiting_wishlist_title"))

    if is_awaiting_title:
        if text.startswith("/"):
            context.user_data["awaiting_wishlist_title"] = False
        elif text in ["By ISBN", "by isbn", "По ISBN", "по isbn", "🔢 По ISBN"]:
            context.user_data["awaiting_wishlist_isbn"] = True
            context.user_data.pop("awaiting_wishlist_title", None)
            await update.effective_message.reply_text(
                text=WISHLIST_ISBN_PROMPT,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_isbn_input_inline_keyboard(),
            )
            return
        else:
            context.user_data["awaiting_wishlist_title"] = False
            wishlist_section.service.add_book(user_id, title=text)
            await update.effective_message.reply_text(
                text=f"✅ Книга *«{text}»* добавлена в ваш вишлист!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=wishlist_section.get_reply_markup(inline=True),
            )
            return

    # Check for direct text commands for Wishlist
    if text in ["Add Book", "➕ Добавить книгу", "Добавить книгу"]:
        if context is not None and hasattr(context, "user_data") and isinstance(context.user_data, dict):
            context.user_data["awaiting_wishlist_title"] = True
            context.user_data.pop("awaiting_wishlist_isbn", None)
            context.user_data.pop("awaiting_wishlist_edit", None)
            context.user_data.pop("pending_isbn_book", None)
        await update.effective_message.reply_text(
            text=WISHLIST_ADD_PROMPT,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_wishlist_add_inline_keyboard(),
        )
        return
    elif text in ["By ISBN", "by isbn", "По ISBN", "по isbn", "🔢 По ISBN", "ISBN"]:
        if context is not None and hasattr(context, "user_data") and isinstance(context.user_data, dict):
            context.user_data["awaiting_wishlist_isbn"] = True
            context.user_data.pop("awaiting_wishlist_title", None)
            context.user_data.pop("awaiting_wishlist_edit", None)
            context.user_data.pop("pending_isbn_book", None)
        await update.effective_message.reply_text(
            text=WISHLIST_ISBN_PROMPT,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_isbn_input_inline_keyboard(),
        )
        return
    elif text in ["GetList", "Get List", "📋 Мой список", "Мой список", "Список книг"]:
        list_text = wishlist_section.service.format_wishlist_text(user_id)
        await update.effective_message.reply_text(
            text=list_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=wishlist_section.get_reply_markup(inline=True),
        )
        return
    elif text in ["Edit", "edit", "✏️ Изменить", "Изменить", "✏️ Редактировать", "Редактировать", "Edit Book"]:
        books = wishlist_section.service.get_wishlist(user_id)
        if not books:
            await update.effective_message.reply_text(
                text=WISHLIST_EMPTY_MESSAGE,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=wishlist_section.get_reply_markup(inline=True),
            )
        else:
            await update.effective_message.reply_text(
                text=WISHLIST_EDIT_PROMPT,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_wishlist_books_inline_keyboard(books, action="edit"),
            )
        return
    elif text in ["Remove", "remove", "🗑 Удалить", "Удалить", "Delete", "delete", "Remove Book"]:
        books = wishlist_section.service.get_wishlist(user_id)
        if not books:
            await update.effective_message.reply_text(
                text=WISHLIST_EMPTY_MESSAGE,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=wishlist_section.get_reply_markup(inline=True),
            )
        else:
            await update.effective_message.reply_text(
                text=WISHLIST_REMOVE_PROMPT,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_wishlist_books_inline_keyboard(books, action="remove"),
            )
        return

    section = default_registry.find_by_text(text)
    if section:
        if section.name == "wishlist":
            await section.handle(update, context)
        else:
            await section.send_response(
                update.effective_message,
                inline=(not section.use_reply_keyboard),
            )
    else:
        await update.effective_message.reply_text(
            text=UNKNOWN_COMMAND_MESSAGE,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_reply_keyboard(),
        )


async def photo_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages, e.g. barcode scanning for wishlist."""
    if not update.effective_message or not update.effective_message.photo:
        return

    telegram_id = (
        update.effective_user.id
        if update.effective_user
        else (update.effective_chat.id if update.effective_chat else 0)
    )
    user_id = get_user_id(telegram_id)

    is_awaiting_isbn = False
    if context is not None and hasattr(context, "user_data") and isinstance(context.user_data, dict):
        is_awaiting_isbn = bool(context.user_data.get("awaiting_wishlist_isbn"))

    if not is_awaiting_isbn:
        return

    photos = update.effective_message.photo
    photo_obj = photos[-1]
    tmp_path = None
    isbn = None

    try:
        file = await context.bot.get_file(photo_obj.file_id)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        await file.download_to_drive(tmp_path)
        isbn = decode_barcode_from_image(tmp_path)
    except Exception as e:
        logger.error(f"Error processing barcode photo: {e}", exc_info=True)
        isbn = None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp photo {tmp_path}: {e}")

    if not isbn:
        # Barcode not scanned from picture -> warn and return to "By ISBN" input
        context.user_data["awaiting_wishlist_isbn"] = True
        await update.effective_message.reply_text(
            text=WISHLIST_BARCODE_NOT_FOUND_MESSAGE,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_isbn_input_inline_keyboard(),
        )
        return

    # Look up book by scanned ISBN
    book = lookup_book_by_isbn(isbn)
    if book:
        context.user_data["pending_isbn_book"] = book
        context.user_data.pop("awaiting_wishlist_isbn", None)
        context.user_data.pop("awaiting_wishlist_title", None)
        await update.effective_message.reply_text(
            text=f"📖 *Найдена книга:*\n\n{book.format_entry()}\n\nДобавить эту книгу в ваш вишлист?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_isbn_confirm_inline_keyboard(),
        )
    else:
        context.user_data.pop("awaiting_wishlist_isbn", None)
        context.user_data["awaiting_wishlist_title"] = True
        await update.effective_message.reply_text(
            text=f"❌ *Книга со штрих-кодом ISBN {isbn} не найдена.*\n\nВы можете попробовать снова или отправить название книги сообщением для добавления вручную:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_wishlist_add_inline_keyboard(),
        )
