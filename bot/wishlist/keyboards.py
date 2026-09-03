"""Keyboards for Wishlist section."""

from typing import Dict, List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.content import (
    BTN_WISHLIST_ADD,
    BTN_WISHLIST_ADD_ISBN,
    BTN_WISHLIST_CANCEL,
    BTN_WISHLIST_CONFIRM,
    BTN_WISHLIST_EDIT,
    BTN_WISHLIST_GET,
    BTN_WISHLIST_REMOVE,
    CB_WISHLIST,
    CB_WISHLIST_ADD,
    CB_WISHLIST_ADD_ISBN,
    CB_WISHLIST_EDIT,
    CB_WISHLIST_GET,
    CB_WISHLIST_REMOVE,
    CB_WL_CANCEL_ISBN,
    CB_WL_CONFIRM_ISBN,
)
from bot.wishlist.book import Book

CB_WL_EDIT_BOOK_PREFIX = "wl_ed_b:"
CB_WL_EDIT_ATTR_PREFIX = "wl_ed_a:"
CB_WL_REMOVE_BOOK_PREFIX = "wl_rm_b:"

BOOK_ATTRIBUTES: Dict[str, str] = {
    "title": "Название",
    "authors": "Автор(ы)",
    "publishing": "Издательство",
    "isbn": "ISBN",
    "year": "Год издания",
    "user_notes": "Заметка",
}

WISHLIST_CALLBACK_MAP = {
    BTN_WISHLIST_ADD: CB_WISHLIST_ADD,
    "Add Book": CB_WISHLIST_ADD,
    "Добавить книгу": CB_WISHLIST_ADD,
    BTN_WISHLIST_ADD_ISBN: CB_WISHLIST_ADD_ISBN,
    "By ISBN": CB_WISHLIST_ADD_ISBN,
    "by isbn": CB_WISHLIST_ADD_ISBN,
    "По ISBN": CB_WISHLIST_ADD_ISBN,
    "по isbn": CB_WISHLIST_ADD_ISBN,
    BTN_WISHLIST_CONFIRM: CB_WL_CONFIRM_ISBN,
    BTN_WISHLIST_CANCEL: CB_WL_CANCEL_ISBN,
    BTN_WISHLIST_GET: CB_WISHLIST_GET,
    "GetList": CB_WISHLIST_GET,
    "Get List": CB_WISHLIST_GET,
    "Мой список": CB_WISHLIST_GET,
    BTN_WISHLIST_EDIT: CB_WISHLIST_EDIT,
    "Edit": CB_WISHLIST_EDIT,
    "Редактировать": CB_WISHLIST_EDIT,
    "Изменить": CB_WISHLIST_EDIT,
    BTN_WISHLIST_REMOVE: CB_WISHLIST_REMOVE,
    "Remove": CB_WISHLIST_REMOVE,
    "Удалить": CB_WISHLIST_REMOVE,
}


def get_wishlist_inline_keyboard() -> InlineKeyboardMarkup:
    """Generate inline keyboard for the wishlist menu."""
    keyboard: List[List[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=BTN_WISHLIST_ADD,
                callback_data=CB_WISHLIST_ADD,
            ),
            InlineKeyboardButton(
                text=BTN_WISHLIST_GET,
                callback_data=CB_WISHLIST_GET,
            ),
        ],
        [
            InlineKeyboardButton(
                text=BTN_WISHLIST_EDIT,
                callback_data=CB_WISHLIST_EDIT,
            ),
            InlineKeyboardButton(
                text=BTN_WISHLIST_REMOVE,
                callback_data=CB_WISHLIST_REMOVE,
            ),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_wishlist_add_inline_keyboard() -> InlineKeyboardMarkup:
    """Generate inline keyboard for the add book menu with 'By ISBN' option."""
    keyboard: List[List[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=BTN_WISHLIST_ADD_ISBN,
                callback_data=CB_WISHLIST_ADD_ISBN,
            ),
        ],
        [
            InlineKeyboardButton(
                text="« Назад в вишлист",
                callback_data=CB_WISHLIST,
            ),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_isbn_input_inline_keyboard() -> InlineKeyboardMarkup:
    """Generate inline keyboard for ISBN/barcode input view."""
    keyboard: List[List[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="« Назад к добавлению книги",
                callback_data=CB_WISHLIST_ADD,
            ),
        ],
        [
            InlineKeyboardButton(
                text="« Меню вишлиста",
                callback_data=CB_WISHLIST,
            ),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_isbn_confirm_inline_keyboard() -> InlineKeyboardMarkup:
    """Generate inline keyboard for confirming book addition found by ISBN."""
    keyboard: List[List[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=BTN_WISHLIST_CONFIRM,
                callback_data=CB_WL_CONFIRM_ISBN,
            ),
            InlineKeyboardButton(
                text=BTN_WISHLIST_CANCEL,
                callback_data=CB_WL_CANCEL_ISBN,
            ),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_wishlist_books_inline_keyboard(books: List[Book], action: str = "edit") -> InlineKeyboardMarkup:
    """Generate inline keyboard listing books for editing or removal."""
    keyboard: List[List[InlineKeyboardButton]] = []
    prefix = CB_WL_EDIT_BOOK_PREFIX if action == "edit" else CB_WL_REMOVE_BOOK_PREFIX
    icon = "📖" if action == "edit" else "🗑"

    for idx, book in enumerate(books, start=1):
        display_title = book.title
        if len(display_title) > 30:
            display_title = display_title[:27] + "..."
        btn_text = f"{icon} {idx}. {display_title}"
        keyboard.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"{prefix}{book.id}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="« Назад в вишлист",
            callback_data=CB_WISHLIST,
        )
    ])
    return InlineKeyboardMarkup(keyboard)


def get_book_attributes_inline_keyboard(book_id: int) -> InlineKeyboardMarkup:
    """Generate inline keyboard for selecting which book attribute to edit."""
    prefix = f"{CB_WL_EDIT_ATTR_PREFIX}{book_id}:"
    keyboard: List[List[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="📖 Название", callback_data=f"{prefix}title"),
            InlineKeyboardButton(text="✍️ Автор(ы)", callback_data=f"{prefix}authors"),
        ],
        [
            InlineKeyboardButton(text="🏢 Издательство", callback_data=f"{prefix}publishing"),
            InlineKeyboardButton(text="🔢 ISBN", callback_data=f"{prefix}isbn"),
        ],
        [
            InlineKeyboardButton(text="📅 Год", callback_data=f"{prefix}year"),
            InlineKeyboardButton(text="📝 Заметка", callback_data=f"{prefix}user_notes"),
        ],
        [
            InlineKeyboardButton(text="« К выбору книги", callback_data=CB_WISHLIST_EDIT),
            InlineKeyboardButton(text="« Меню вишлиста", callback_data=CB_WISHLIST),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
