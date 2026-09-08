"""Telegram bot command, message, and callback handlers."""

import inspect
import io
import logging
import os
import tempfile

from PIL import Image
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.analytics.anonymizer import anonymize_user_id
from bot.analytics.service import default_analytics_service
from bot.content import (
    BTN_SHOW_STANDS,
    BTN_SHOW_STANDS_INFO,
    BTN_TIMETABLE,
    CB_CHILDREN_ACTIVITY,
    CB_HELP,
    CB_MAP,
    CB_MASTER_CLASSES,
    CB_MC_FILTER_ALL,
    CB_MC_FILTER_CHILDREN,
    CB_MC_ITEM_PREFIX,
    CB_PARTICIPANTS,
    CB_RECOMMENDATIONS,
    CB_STANDS,
    CB_STAND_PREFIX,
    CB_TIMETABLE,
    CB_WISHLIST,
    MAX_PHOTO_SIZE_BYTES,
    UNKNOWN_COMMAND_MESSAGE,
    WISHLIST_ADD_PROMPT,
    WISHLIST_BARCODE_NOT_FOUND_MESSAGE,
    WISHLIST_EDIT_PROMPT,
    WISHLIST_EMPTY_MESSAGE,
    WISHLIST_ISBN_INVALID_MESSAGE,
    WISHLIST_ISBN_NOT_FOUND_MESSAGE,
    WISHLIST_ISBN_PROMPT,
    WISHLIST_PHOTO_TOO_LARGE_MESSAGE,
    WISHLIST_REMOVE_PROMPT,
)
from bot.keyboards import get_main_reply_keyboard
from bot.participants.keyboards import (
    CB_PART_ITEM_PREFIX,
    CB_PARTICIPANTS_LIST,
)
from bot.timetable.keyboards import (
    CB_TT_DATES,
    CB_TT_DATE_PREFIX,
    CB_TT_LOC_PREFIX,
)
from bot.sections import (
    ChildrenActivity,
    Help,
    Map,
    MasterClasses,
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
    CB_WL_CANCEL_ISBN,
    CB_WL_CONFIRM_ISBN,
    CB_WL_EDIT_ATTR_PREFIX,
    CB_WL_EDIT_BOOK_PREFIX,
    CB_WL_REMOVE_BOOK_PREFIX,
    get_book_added_inline_keyboard,
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
master_classes_section = MasterClasses()
recommendations_section = Recommendations()
participants_section = Participants()
wishlist_section = Wishlist()


def _get_anonymized_user_id(update: Update) -> str:
    """Extract anonymized user ID from telegram update."""
    telegram_id = (
        update.effective_user.id
        if update.effective_user
        else (update.effective_chat.id if update.effective_chat else 0)
    )
    return anonymize_user_id(telegram_id)


def _resolve_callback_button_label(query) -> str:
    """Resolve human-readable Russian label for an inline button click, including programmatically generated items."""
    data = (query.data or "").strip() if query else ""
    if not data:
        return "Кнопка"

    # 1. Check if the button is present in the message reply markup
    if query.message and getattr(query.message, "reply_markup", None):
        inline_kb = getattr(query.message.reply_markup, "inline_keyboard", None)
        if inline_kb:
            for row in inline_kb:
                for btn in row:
                    if getattr(btn, "callback_data", None) == data:
                        text = getattr(btn, "text", "")
                        if text:
                            return text.strip()

    # 2. Master class item buttons (date and event name)
    if data.startswith(CB_MC_ITEM_PREFIX) or data.startswith("mc_item:"):
        parts = data.split(":")
        if len(parts) >= 3:
            date_str = parts[1]
            try:
                idx = int(parts[2])
                from bot.timetable.service import TimetableService
                events = TimetableService().get_events_by_date(date_str)
                mc_events = [e for e in events if getattr(e, "is_master_class", False)]
                if 0 <= idx < len(mc_events):
                    ev = mc_events[idx]
                    return f"{ev.title}"
            except Exception:
                pass
        return "Мастер-класс"

    # 3. Timetable date selection buttons
    if (
        data.startswith(CB_TT_DATE_PREFIX)
        or data.startswith("tt_date:")
        or data.startswith("tt_d:")
        or data.startswith("ca_date:")
    ):
        date_str = data.split(":", 1)[1] if ":" in data else data
        try:
            from bot.timetable.service import TimetableService
            day = TimetableService().get_timetable_by_date(date_str)
            if day and hasattr(day, "format_date_display"):
                return day.format_date_display()
        except Exception:
            pass
        return date_str

    # 4. Timetable location selection
    if data.startswith(CB_TT_LOC_PREFIX) or data.startswith("tt_loc:") or data.startswith("ca_loc:"):
        loc_part = data.split(":", 1)[1] if ":" in data else data
        return f"Площадка: {loc_part}"

    # 5. Stand buttons
    if data.startswith(CB_STAND_PREFIX) or data.startswith("stand:"):
        stand_part = data.split(":", 1)[1] if ":" in data else data
        try:
            from bot.participants.service import ParticipantsService
            stands = ParticipantsService().get_stands()
            if stand_part.isdigit() and int(stand_part) < len(stands):
                return f"Стенд {stands[int(stand_part)]}"
        except Exception:
            pass
        return f"Стенд {stand_part}"

    # 6. Participant item buttons
    if data.startswith(CB_PART_ITEM_PREFIX) or data.startswith("part_item:"):
        item_part = data.split(":", 1)[1] if ":" in data else data
        raw_idx = item_part.split(":")[0]
        try:
            from bot.participants.service import ParticipantsService
            parts_list = ParticipantsService().get_participants()
            if raw_idx.isdigit() and int(raw_idx) < len(parts_list):
                return parts_list[int(raw_idx)].format_button_label()
        except Exception:
            pass
        return f"Участник {raw_idx}"

    # 7. Wishlist buttons
    if data.startswith(CB_WL_EDIT_BOOK_PREFIX) or data.startswith("wl_edit_bk:"):
        return "Редактировать книгу"
    if data.startswith(CB_WL_REMOVE_BOOK_PREFIX) or data.startswith("wl_rm_bk:"):
        return "Удалить книгу"
    if data.startswith(CB_WL_EDIT_ATTR_PREFIX) or data.startswith("wl_attr:"):
        return "Изменить поле"

    # 8. Known static callback labels
    static_labels = {
        CB_MAP: "Карта",
        "action_map": "Карта",
        "map": "Карта",
        CB_TIMETABLE: "Расписание",
        "action_timetable": "Расписание",
        "timetable": "Расписание",
        "timetables": "Расписание",
        CB_TT_DATES: "Расписание",
        "ca_dates": "Детская программа",
        CB_CHILDREN_ACTIVITY: "Детская программа",
        "section_children_activity": "Детская программа",
        "children": "Детская программа",
        CB_MASTER_CLASSES: "Мастер-классы",
        "action_master_classes": "Мастер-классы",
        "masterclasses": "Мастер-классы",
        CB_MC_FILTER_CHILDREN: "Для детей",
        "mc_filter:children": "Для детей",
        CB_MC_FILTER_ALL: "Все мастер-классы",
        "mc_filter:all": "Все мастер-классы",
        CB_RECOMMENDATIONS: "Рекомендации",
        "action_recommendations": "Рекомендации",
        "recommendations": "Рекомендации",
        CB_PARTICIPANTS: "Участники",
        "action_participants": "Участники",
        "participants": "Участники",
        CB_PARTICIPANTS_LIST: "Участники",
        "participants_list": "Участники",
        CB_STANDS: "Стенды",
        "action_stands": "Стенды",
        "stands": "Стенды",
        CB_WISHLIST: "Вишлист",
        "action_wishlist": "Вишлист",
        "wishlist": "Вишлист",
        "wishlist_add": "Добавить книгу",
        "wl_add_isbn": "По ISBN",
        "wl_conf_isbn": "Подтвердить ISBN",
        "wl_canc_isbn": "Отмена",
        "wishlist_get": "Мой список",
        "wishlist_edit": "Редактировать",
        "wishlist_remove": "Удалить",
        CB_HELP: "Помощь",
        "action_help": "Помощь",
        "help": "Помощь",
    }

    if data in static_labels:
        return static_labels[data]

    section = default_registry.find_by_callback(data)
    if section:
        if hasattr(section, "button_text") and section.button_text:
            return section.button_text
        return section.name

    return data


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    uid = _get_anonymized_user_id(update)
    default_analytics_service.record_chat_interaction(uid)
    default_analytics_service.record_command(uid, "/start")
    await start_section.handle(update, context)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    uid = _get_anonymized_user_id(update)
    default_analytics_service.record_command(uid, "/help")
    await help_section.handle(update, context)


async def map_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /map command."""
    uid = _get_anonymized_user_id(update)
    default_analytics_service.record_command(uid, "/map")
    await map_section.handle(update, context)


async def timetable_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /timetables command."""
    uid = _get_anonymized_user_id(update)
    default_analytics_service.record_command(uid, "/timetables")
    await timetable_section.handle(update, context)


async def children_activity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /children and /children_activity commands."""
    uid = _get_anonymized_user_id(update)
    default_analytics_service.record_command(uid, "/children")
    await children_activity_section.handle(update, context)


async def master_classes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /masterclasses, /masterclass, and /mc commands."""
    uid = _get_anonymized_user_id(update)
    default_analytics_service.record_command(uid, "/masterclasses")
    await master_classes_section.handle(update, context)


async def recommendations_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /recommendations and /recs commands."""
    uid = _get_anonymized_user_id(update)
    default_analytics_service.record_command(uid, "/recommendations")
    await recommendations_section.handle(update, context)


async def participants_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /participants, /stands, and /vendors commands."""
    uid = _get_anonymized_user_id(update)
    msg_text = update.effective_message.text.strip().lower() if update.effective_message and update.effective_message.text else ""
    if "stand" in msg_text or "стенд" in msg_text:
        default_analytics_service.record_command(uid, "/stands")
    else:
        default_analytics_service.record_command(uid, "/participants")
    await participants_section.handle(update, context)


async def wishlist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /wishlist, /getlist, and /addbook commands."""
    uid = _get_anonymized_user_id(update)
    raw_cmd = "/wishlist"
    if update.effective_message and update.effective_message.text and update.effective_message.text.startswith("/"):
        raw_cmd = update.effective_message.text.strip().split()[0]
    default_analytics_service.record_command(uid, raw_cmd)
    await wishlist_section.handle(update, context)


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callback queries."""
    query = update.callback_query
    if not query:
        return

    uid = _get_anonymized_user_id(update)
    button_label = _resolve_callback_button_label(query)
    default_analytics_service.record_inline_keyboard_event(
        user_id=uid,
        callback_data=query.data,
        button_name=button_label,
    )
    default_analytics_service.record_command(uid, button_label)

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
                    default_analytics_service.record_command(user_id, "ISBN: success")
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
                    default_analytics_service.record_command(user_id, "ISBN: failure in isbn lookup")
                    context.user_data.pop("awaiting_wishlist_isbn", None)
                    context.user_data["awaiting_wishlist_title"] = True
                    await update.effective_message.reply_text(
                        text=f"❌ *Книга по указанному ISBN ({cleaned_isbn}) не найдена.*\n\nВы можете попробовать еще раз или отправить название книги сообщением для добавления вручную:",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_wishlist_add_inline_keyboard(),
                    )
                    return
            else:
                default_analytics_service.record_command(user_id, "ISBN: failure in isbn lookup")
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
            default_analytics_service.record_command(user_id, "По ISBN")
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
            added_book = wishlist_section.service.add_book(user_id, title=text)
            default_analytics_service.record_command(user_id, "Добавить книгу")
            await update.effective_message.reply_text(
                text=f"✅ Книга *«{text}»* добавлена в ваш вишлист!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_book_added_inline_keyboard(added_book.id),
            )
            return

    # Check for direct text commands for Wishlist
    if text in ["Add Book", "➕ Добавить книгу", "Добавить книгу"]:
        default_analytics_service.record_command(user_id, "Добавить книгу")
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
        default_analytics_service.record_command(user_id, "По ISBN")
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
        default_analytics_service.record_command(user_id, "Мой список")
        list_text = wishlist_section.service.format_wishlist_text(user_id)
        await update.effective_message.reply_text(
            text=list_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=wishlist_section.get_reply_markup(inline=True),
        )
        return
    elif text in ["Edit", "edit", "✏️ Изменить", "Изменить", "✏️ Редактировать", "Редактировать", "Edit Book"]:
        default_analytics_service.record_command(user_id, "Редактировать")
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
        default_analytics_service.record_command(user_id, "Удалить")
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

    uid = _get_anonymized_user_id(update)
    section = default_registry.find_by_text(text)
    if section:
        if text in ["стенды", "стенд", "stands", "stand", "📍 Информация о стендах", "Информация о стендах", BTN_SHOW_STANDS, BTN_SHOW_STANDS_INFO]:
            default_analytics_service.record_command(uid, "Информация о стендах")
        elif text in ["расписание", "программа", "timetable", "timetables", "schedule", "time table", BTN_TIMETABLE]:
            default_analytics_service.record_command(uid, "Расписание")
        else:
            label = section.button_text if hasattr(section, "button_text") and section.button_text else text
            default_analytics_service.record_command(uid, label)

        if section.name == "wishlist":
            await section.handle(update, context)
        else:
            await section.send_response(
                update.effective_message,
                inline=(not section.use_reply_keyboard),
            )
    else:
        default_analytics_service.record_unrecognized_message(uid, text)
        default_analytics_service.record_command(uid, "Неожиданный ввод")
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

    # Check photo size limit before downloading
    if photo_obj.file_size and photo_obj.file_size > MAX_PHOTO_SIZE_BYTES:
        default_analytics_service.record_command(user_id, "ISBN: failure in recognizing pic")
        context.user_data["awaiting_wishlist_isbn"] = True
        await update.effective_message.reply_text(
            text=WISHLIST_PHOTO_TOO_LARGE_MESSAGE,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_isbn_input_inline_keyboard(),
        )
        return

    isbn = None

    try:
        file = await context.bot.get_file(photo_obj.file_id)
        if file.file_size and file.file_size > MAX_PHOTO_SIZE_BYTES:
            default_analytics_service.record_command(user_id, "ISBN: failure in recognizing pic")
            context.user_data["awaiting_wishlist_isbn"] = True
            await update.effective_message.reply_text(
                text=WISHLIST_PHOTO_TOO_LARGE_MESSAGE,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_isbn_input_inline_keyboard(),
            )
            return

        image_bytes = await file.download_as_bytearray()
        if len(image_bytes) > MAX_PHOTO_SIZE_BYTES:
            default_analytics_service.record_command(user_id, "ISBN: failure in recognizing pic")
            context.user_data["awaiting_wishlist_isbn"] = True
            await update.effective_message.reply_text(
                text=WISHLIST_PHOTO_TOO_LARGE_MESSAGE,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_isbn_input_inline_keyboard(),
            )
            return

        image = Image.open(io.BytesIO(image_bytes))
        isbn = decode_barcode_from_image(image)
    except Exception as e:
        logger.error(f"Error processing barcode photo: {e}", exc_info=True)
        isbn = None

    if not isbn:
        # Barcode not scanned from picture -> warn and return to "By ISBN" input
        default_analytics_service.record_command(user_id, "ISBN: failure in recognizing pic")
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
        default_analytics_service.record_command(user_id, "ISBN: success")
        context.user_data["pending_isbn_book"] = book
        context.user_data.pop("awaiting_wishlist_isbn", None)
        context.user_data.pop("awaiting_wishlist_title", None)
        await update.effective_message.reply_text(
            text=f"📖 *Найдена книга:*\n\n{book.format_entry()}\n\nДобавить эту книгу в ваш вишлист?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_isbn_confirm_inline_keyboard(),
        )
    else:
        default_analytics_service.record_command(user_id, "ISBN: failure in isbn lookup")
        context.user_data.pop("awaiting_wishlist_isbn", None)
        context.user_data["awaiting_wishlist_title"] = True
        await update.effective_message.reply_text(
            text=f"❌ *Книга со штрих-кодом ISBN {isbn} не найдена.*\n\nВы можете попробовать снова или отправить название книги сообщением для добавления вручную:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_wishlist_add_inline_keyboard(),
        )
