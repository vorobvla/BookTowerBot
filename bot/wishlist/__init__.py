"""Wishlist package for booktower bot."""

from bot.wishlist.book import Book
from bot.wishlist.keyboards import (
    BOOK_ATTRIBUTES,
    CB_WL_EDIT_ATTR_PREFIX,
    CB_WL_EDIT_BOOK_PREFIX,
    CB_WL_REMOVE_BOOK_PREFIX,
    WISHLIST_CALLBACK_MAP,
    get_book_attributes_inline_keyboard,
    get_wishlist_books_inline_keyboard,
    get_wishlist_inline_keyboard,
)
from bot.wishlist.service import WishlistService, get_user_id

__all__ = [
    "Book",
    "WishlistService",
    "get_user_id",
    "get_wishlist_inline_keyboard",
    "get_wishlist_books_inline_keyboard",
    "get_book_attributes_inline_keyboard",
    "WISHLIST_CALLBACK_MAP",
    "BOOK_ATTRIBUTES",
    "CB_WL_EDIT_BOOK_PREFIX",
    "CB_WL_EDIT_ATTR_PREFIX",
    "CB_WL_REMOVE_BOOK_PREFIX",
]
