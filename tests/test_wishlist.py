"""Tests for user wishlist database, service, keyboards, section, and bot handlers."""

import os
import sqlite3
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from telegram import Update
from telegram.constants import ParseMode

from bot.content import (
    BTN_WISHLIST,
    BTN_WISHLIST_ADD,
    BTN_WISHLIST_EDIT,
    BTN_WISHLIST_GET,
    BTN_WISHLIST_REMOVE,
    BUTTON_CALLBACK_MAP,
    CB_WISHLIST,
    CB_WISHLIST_ADD,
    CB_WISHLIST_EDIT,
    CB_WISHLIST_GET,
    CB_WISHLIST_REMOVE,
    WISHLIST_ADD_PROMPT,
    WISHLIST_EDIT_PROMPT,
    WISHLIST_EMPTY_MESSAGE,
    WISHLIST_MESSAGE,
    WISHLIST_REMOVE_PROMPT,
)
from bot.handlers import (
    button_callback_handler,
    text_message_handler,
    wishlist_handler,
    wishlist_section,
)
from bot.keyboards import (
    get_main_inline_keyboard,
    get_main_reply_keyboard,
)
from bot.sections.wishlist import Wishlist
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


# ==============================================================================
# Domain Model Tests
# ==============================================================================


def test_book_model_required_title():
    with pytest.raises(ValueError):
        Book(title="")

    with pytest.raises(ValueError):
        Book(title="   ")

    book = Book(title="  Мастер и Маргарита  ")
    assert book.title == "Мастер и Маргарита"
    assert book.authors is None
    assert book.publishing is None
    assert book.isbn is None
    assert book.year is None
    assert book.user_notes is None


def test_book_model_all_attributes():
    book = Book(
        title="1984",
        authors="Джордж Оруэлл",
        publishing="ACT",
        isbn="978-5-17-090336-8",
        year=2021,
        user_notes="Купить в подарок",
        id=1,
    )
    assert book.title == "1984"
    assert book.authors == "Джордж Оруэлл"
    assert book.publishing == "ACT"
    assert book.isbn == "978-5-17-090336-8"
    assert book.year == 2021
    assert book.user_notes == "Купить в подарок"
    assert book.id == 1

    entry = book.format_entry(index=1)
    assert "1. *«1984»*" in entry
    assert "Джордж Оруэлл" in entry
    assert "Изд: ACT" in entry
    assert "2021 г." in entry
    assert "ISBN: 978-5-17-090336-8" in entry
    assert "Заметка: Купить в подарок" in entry


# ==============================================================================
# Hashing & Anonymization Tests
# ==============================================================================


def test_get_user_id_hashing(monkeypatch):
    telegram_id = 123456789
    salt1 = "test_salt_alpha"
    salt2 = "test_salt_beta"

    monkeypatch.setenv("WISHLIST_SALT", salt1)
    user_id_1 = get_user_id(telegram_id)

    monkeypatch.setenv("WISHLIST_SALT", salt2)
    user_id_2 = get_user_id(telegram_id)

    monkeypatch.setenv("WISHLIST_SALT", salt1)
    user_id_3 = get_user_id(987654321)

    # 64-char sha256 hex string
    assert len(user_id_1) == 64
    assert str(telegram_id) not in user_id_1

    # Different salts produce different hashes
    assert user_id_1 != user_id_2

    # Different telegram_ids produce different hashes
    assert user_id_1 != user_id_3

    # Deterministic for same inputs
    monkeypatch.setenv("WISHLIST_SALT", salt1)
    assert user_id_1 == get_user_id(telegram_id)


# ==============================================================================
# Database & Service Tests
# ==============================================================================


@pytest.fixture
def temp_service():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    service = WishlistService(db_path=db_path, salt="test_salt")
    yield service
    if os.path.exists(db_path):
        os.remove(db_path)


def test_database_schema(temp_service):
    with temp_service._get_connection() as conn:
        cursor = conn.cursor()
        # Check users table
        cursor.execute("PRAGMA table_info(users);")
        user_cols = {row["name"] for row in cursor.fetchall()}
        assert user_cols == {"user_id"}  # user has no other attributes

        # Check wishlist_books table
        cursor.execute("PRAGMA table_info(wishlist_books);")
        book_cols = {row["name"] for row in cursor.fetchall()}
        expected_cols = {"id", "user_id", "title", "authors", "publishing", "isbn", "year", "user_notes", "created_at"}
        assert expected_cols.issubset(book_cols)


def test_add_and_get_wishlist(temp_service):
    user_id = "test_user_123"
    assert temp_service.get_wishlist(user_id) == []

    # Add book with only title
    book1 = temp_service.add_book(user_id, title="Бесы")
    assert book1.id is not None
    assert book1.title == "Бесы"

    # Add book with full attributes
    book2 = temp_service.add_book(
        user_id,
        title="Преступление и наказание",
        authors="Ф. М. Достоевский",
        publishing="Азбука",
        year=2020,
    )
    assert book2.id is not None
    assert book2.title == "Преступление и наказание"

    wishlist = temp_service.get_wishlist(user_id)
    assert len(wishlist) == 2
    assert wishlist[0].title == "Бесы"
    assert wishlist[1].title == "Преступление и наказание"
    assert wishlist[1].authors == "Ф. М. Достоевский"


def test_format_wishlist_text(temp_service):
    user_id = "user_456"
    empty_text = temp_service.format_wishlist_text(user_id)
    assert "пуст" in empty_text

    temp_service.add_book(user_id, title="Гарри Поттер")
    temp_service.add_book(user_id, title="Властелин Колец")
    text = temp_service.format_wishlist_text(user_id)
    assert "Ваш список покупок" in text
    assert "1. *«Гарри Поттер»*" in text
    assert "2. *«Властелин Колец»*" in text


def test_delete_and_clear_wishlist(temp_service):
    user_id = "user_789"
    b1 = temp_service.add_book(user_id, title="Книга 1")
    b2 = temp_service.add_book(user_id, title="Книга 2")

    assert temp_service.delete_book(user_id, b1.id) is True
    assert len(temp_service.get_wishlist(user_id)) == 1

    temp_service.clear_wishlist(user_id)
    assert len(temp_service.get_wishlist(user_id)) == 0


def test_get_and_update_book(temp_service):
    user_id = "user_update_123"
    b = temp_service.add_book(user_id, title="Original Title", authors="Author 1")
    assert b.id is not None

    # Get single book
    fetched = temp_service.get_book(user_id, b.id)
    assert fetched is not None
    assert fetched.title == "Original Title"
    assert fetched.authors == "Author 1"

    # Non-existent book
    assert temp_service.get_book(user_id, 99999) is None

    # Update individual attributes
    up1 = temp_service.update_book_attribute(user_id, b.id, "title", "New Title")
    assert up1.title == "New Title"

    up2 = temp_service.update_book_attribute(user_id, b.id, "year", "2025")
    assert up2.year == 2025

    up3 = temp_service.update_book_attribute(user_id, b.id, "publishing", "MIF")
    assert up3.publishing == "MIF"

    up4 = temp_service.update_book_attribute(user_id, b.id, "isbn", "123-456")
    assert up4.isbn == "123-456"

    up5 = temp_service.update_book_attribute(user_id, b.id, "user_notes", "Interesting read")
    assert up5.user_notes == "Interesting read"

    # Empty title should raise ValueError
    with pytest.raises(ValueError):
        temp_service.update_book_attribute(user_id, b.id, "title", "  ")

    # Invalid year should raise ValueError
    with pytest.raises(ValueError):
        temp_service.update_book_attribute(user_id, b.id, "year", "not_a_year")

    # Invalid attribute should raise ValueError
    with pytest.raises(ValueError):
        temp_service.update_book_attribute(user_id, b.id, "non_existing_field", "value")

    # Update full book
    b.title = "Completely Updated Title"
    b.year = 2026
    updated_full = temp_service.update_book(user_id, b)
    assert updated_full.title == "Completely Updated Title"
    assert updated_full.year == 2026


# ==============================================================================
# Keyboard & Section Tests
# ==============================================================================


def test_wishlist_inline_keyboard():
    kb = get_wishlist_inline_keyboard()
    assert len(kb.inline_keyboard) == 2
    assert len(kb.inline_keyboard[0]) == 2
    assert len(kb.inline_keyboard[1]) == 2
    add_btn, get_btn = kb.inline_keyboard[0]
    edit_btn, rm_btn = kb.inline_keyboard[1]

    assert add_btn.text == BTN_WISHLIST_ADD
    assert add_btn.callback_data == CB_WISHLIST_ADD
    assert get_btn.text == BTN_WISHLIST_GET
    assert get_btn.callback_data == CB_WISHLIST_GET
    assert edit_btn.text == BTN_WISHLIST_EDIT
    assert edit_btn.callback_data == CB_WISHLIST_EDIT
    assert rm_btn.text == BTN_WISHLIST_REMOVE
    assert rm_btn.callback_data == CB_WISHLIST_REMOVE


def test_wishlist_books_inline_keyboard():
    books = [
        Book(id=1, title="Краткое название"),
        Book(id=2, title="Очень длинное название книги, которое обязательно должно быть сокращено"),
    ]
    kb_edit = get_wishlist_books_inline_keyboard(books, action="edit")
    assert len(kb_edit.inline_keyboard) == 3
    assert kb_edit.inline_keyboard[0][0].callback_data == "wl_ed_b:1"
    assert "1. Краткое название" in kb_edit.inline_keyboard[0][0].text
    assert kb_edit.inline_keyboard[1][0].callback_data == "wl_ed_b:2"
    assert "..." in kb_edit.inline_keyboard[1][0].text
    assert kb_edit.inline_keyboard[2][0].callback_data == CB_WISHLIST

    kb_remove = get_wishlist_books_inline_keyboard(books, action="remove")
    assert kb_remove.inline_keyboard[0][0].callback_data == "wl_rm_b:1"
    assert "🗑" in kb_remove.inline_keyboard[0][0].text


def test_book_attributes_inline_keyboard():
    kb = get_book_attributes_inline_keyboard(42)
    # 3 rows of 2 attributes + 1 row of navigation buttons
    assert len(kb.inline_keyboard) == 4
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "wl_ed_a:42:title" in callbacks
    assert "wl_ed_a:42:authors" in callbacks
    assert "wl_ed_a:42:publishing" in callbacks
    assert "wl_ed_a:42:isbn" in callbacks
    assert "wl_ed_a:42:year" in callbacks
    assert "wl_ed_a:42:user_notes" in callbacks
    assert CB_WISHLIST_EDIT in callbacks
    assert CB_WISHLIST in callbacks


@pytest.mark.asyncio
async def test_wishlist_section_matching():
    sec = Wishlist()
    assert sec.name == "wishlist"
    assert sec.matches_command("wishlist")
    assert sec.matches_command("/wishlist")
    assert sec.matches_command("getlist")
    assert sec.matches_command("addbook")
    assert sec.matches_command("editbook")
    assert sec.matches_command("removebook")
    assert sec.matches_callback(CB_WISHLIST)
    assert sec.matches_callback(CB_WISHLIST_ADD)
    assert sec.matches_callback(CB_WISHLIST_GET)
    assert sec.matches_callback(CB_WISHLIST_EDIT)
    assert sec.matches_callback(CB_WISHLIST_REMOVE)
    assert sec.matches_callback("wl_ed_b:1")
    assert sec.matches_callback("wl_ed_a:1:title")
    assert sec.matches_callback("wl_rm_b:1")
    assert sec.matches_text(BTN_WISHLIST)
    assert sec.matches_text("Wishlist")
    assert sec.matches_text("список покупок")


@pytest.mark.asyncio
async def test_wishlist_section_callbacks(temp_service):
    sec = Wishlist(service=temp_service)

    # 1. Callback action_wishlist
    query_main = AsyncMock()
    query_main.data = CB_WISHLIST
    query_main.edit_message_text = AsyncMock()
    await sec.handle_callback_query(query_main)
    query_main.edit_message_text.assert_awaited_once()
    assert query_main.edit_message_text.call_args.kwargs["text"] == WISHLIST_MESSAGE

    # 2. Callback wishlist_add sets awaiting flag
    context = MagicMock()
    context.user_data = {}
    query_add = AsyncMock()
    query_add.data = CB_WISHLIST_ADD
    query_add.edit_message_text = AsyncMock()
    await sec.handle_callback_query(query_add, context=context)
    assert context.user_data.get("awaiting_wishlist_title") is True
    assert query_add.edit_message_text.call_args.kwargs["text"] == WISHLIST_ADD_PROMPT

    # 3. Callback wishlist_get displays user's wishlist
    query_get = AsyncMock()
    query_get.data = CB_WISHLIST_GET
    query_get.from_user = MagicMock(id=999)
    query_get.edit_message_text = AsyncMock()
    await sec.handle_callback_query(query_get)
    query_get.edit_message_text.assert_awaited_once()
    assert "пуст" in query_get.edit_message_text.call_args.kwargs["text"]

    # 4. Callback wishlist_edit with no books
    query_edit_empty = AsyncMock()
    query_edit_empty.data = CB_WISHLIST_EDIT
    query_edit_empty.from_user = MagicMock(id=999)
    query_edit_empty.edit_message_text = AsyncMock()
    await sec.handle_callback_query(query_edit_empty)
    assert query_edit_empty.edit_message_text.call_args.kwargs["text"] == WISHLIST_EMPTY_MESSAGE

    # Add a book for user 999
    user_id = get_user_id(999)
    book = temp_service.add_book(user_id, title="Test Book")

    # 5. Callback wishlist_edit with books shows list of books
    query_edit_books = AsyncMock()
    query_edit_books.data = CB_WISHLIST_EDIT
    query_edit_books.from_user = MagicMock(id=999)
    query_edit_books.edit_message_text = AsyncMock()
    await sec.handle_callback_query(query_edit_books)
    assert query_edit_books.edit_message_text.call_args.kwargs["text"] == WISHLIST_EDIT_PROMPT

    # 6. Callback tap on specific book to edit (wl_ed_b:<id>) shows attributes
    query_book_select = AsyncMock()
    query_book_select.data = f"wl_ed_b:{book.id}"
    query_book_select.from_user = MagicMock(id=999)
    query_book_select.edit_message_text = AsyncMock()
    await sec.handle_callback_query(query_book_select)
    assert "Редактирование книги" in query_book_select.edit_message_text.call_args.kwargs["text"]

    # 7. Callback tap on attribute (wl_ed_a:<id>:year) prompts for input
    query_attr_select = AsyncMock()
    query_attr_select.data = f"wl_ed_a:{book.id}:year"
    query_attr_select.from_user = MagicMock(id=999)
    query_attr_select.edit_message_text = AsyncMock()
    await sec.handle_callback_query(query_attr_select, context=context)
    assert context.user_data.get("awaiting_wishlist_edit") == {"book_id": book.id, "attribute": "year"}
    assert "Год" in query_attr_select.edit_message_text.call_args.kwargs["text"]

    # 8. Callback remove book (wl_rm_b:<id>) deletes book
    query_rm = AsyncMock()
    query_rm.data = f"wl_rm_b:{book.id}"
    query_rm.from_user = MagicMock(id=999)
    query_rm.edit_message_text = AsyncMock()
    await sec.handle_callback_query(query_rm)
    assert "удалена" in query_rm.edit_message_text.call_args.kwargs["text"]
    assert len(temp_service.get_wishlist(user_id)) == 0


# ==============================================================================
# Handler Interaction Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_wishlist_add_and_get_handler_flow():
    context = MagicMock()
    context.user_data = {}

    # Step 1: User enters wishlist via /addbook or button "Add Book"
    update_add_btn = MagicMock(spec=Update)
    update_add_btn.effective_message = AsyncMock(text="Add Book")
    update_add_btn.effective_user = MagicMock(id=111222)
    await text_message_handler(update_add_btn, context)
    assert context.user_data.get("awaiting_wishlist_title") is True
    update_add_btn.effective_message.reply_text.assert_awaited_once()
    assert update_add_btn.effective_message.reply_text.call_args.kwargs["text"] == WISHLIST_ADD_PROMPT

    # Step 2: User sends book title text
    update_title = MagicMock(spec=Update)
    update_title.effective_message = AsyncMock(text="Маленький принц")
    update_title.effective_user = MagicMock(id=111222)
    await text_message_handler(update_title, context)
    assert context.user_data.get("awaiting_wishlist_title") is False
    update_title.effective_message.reply_text.assert_awaited_once()
    reply_text = update_title.effective_message.reply_text.call_args.kwargs["text"]
    assert "Маленький принц" in reply_text
    assert "добавлена" in reply_text

    # Step 3: User requests wishlist via "GetList"
    update_get = MagicMock(spec=Update)
    update_get.effective_message = AsyncMock(text="GetList")
    update_get.effective_user = MagicMock(id=111222)
    await text_message_handler(update_get, context)
    update_get.effective_message.reply_text.assert_awaited_once()
    get_text = update_get.effective_message.reply_text.call_args.kwargs["text"]
    assert "Маленький принц" in get_text


@pytest.mark.asyncio
async def test_wishlist_edit_and_remove_handler_flow():
    context = MagicMock()
    context.user_data = {}

    user_id = get_user_id(333444)
    book = wishlist_section.service.add_book(user_id, title="Война и мир", authors="Л. Толстой")

    # Step 1: User sends text "Edit"
    update_edit_btn = MagicMock(spec=Update)
    update_edit_btn.effective_message = AsyncMock(text="Edit")
    update_edit_btn.effective_user = MagicMock(id=333444)
    await text_message_handler(update_edit_btn, context)
    update_edit_btn.effective_message.reply_text.assert_awaited_once()
    assert update_edit_btn.effective_message.reply_text.call_args.kwargs["text"] == WISHLIST_EDIT_PROMPT

    # Step 2: Set awaiting_wishlist_edit state for attribute "year"
    context.user_data["awaiting_wishlist_edit"] = {"book_id": book.id, "attribute": "year"}

    # Invalid year
    update_year_invalid = MagicMock(spec=Update)
    update_year_invalid.effective_message = AsyncMock(text="not_a_number")
    update_year_invalid.effective_user = MagicMock(id=333444)
    await text_message_handler(update_year_invalid, context)
    assert "числом" in update_year_invalid.effective_message.reply_text.call_args.kwargs["text"]

    # Valid year
    context.user_data["awaiting_wishlist_edit"] = {"book_id": book.id, "attribute": "year"}
    update_year = MagicMock(spec=Update)
    update_year.effective_message = AsyncMock(text="1869")
    update_year.effective_user = MagicMock(id=333444)
    await text_message_handler(update_year, context)
    assert context.user_data.get("awaiting_wishlist_edit") is None
    reply_year_text = update_year.effective_message.reply_text.call_args.kwargs["text"]
    assert "обновлено" in reply_year_text
    assert "1869 г." in reply_year_text
    reply_year_markup = update_year.effective_message.reply_text.call_args.kwargs["reply_markup"]
    year_cbs = [btn.callback_data for row in reply_year_markup.inline_keyboard for btn in row]
    assert f"wl_ed_a:{book.id}:title" in year_cbs
    assert f"wl_ed_a:{book.id}:year" in year_cbs

    # Step 3: Edit title
    context.user_data["awaiting_wishlist_edit"] = {"book_id": book.id, "attribute": "title"}
    update_title_empty = MagicMock(spec=Update)
    update_title_empty.effective_message = AsyncMock(text="")
    update_title_empty.effective_user = MagicMock(id=333444)
    # Empty message will return early if text is empty
    context.user_data["awaiting_wishlist_edit"] = {"book_id": book.id, "attribute": "title"}
    update_title_new = MagicMock(spec=Update)
    update_title_new.effective_message = AsyncMock(text="Война и мир (том 1)")
    update_title_new.effective_user = MagicMock(id=333444)
    await text_message_handler(update_title_new, context)
    assert "Война и мир (том 1)" in update_title_new.effective_message.reply_text.call_args.kwargs["text"]
    reply_title_markup = update_title_new.effective_message.reply_text.call_args.kwargs["reply_markup"]
    title_cbs = [btn.callback_data for row in reply_title_markup.inline_keyboard for btn in row]
    assert f"wl_ed_a:{book.id}:title" in title_cbs
    assert f"wl_ed_a:{book.id}:authors" in title_cbs

    # Step 4: User sends text "Remove"
    update_remove_btn = MagicMock(spec=Update)
    update_remove_btn.effective_message = AsyncMock(text="Remove")
    update_remove_btn.effective_user = MagicMock(id=333444)
    await text_message_handler(update_remove_btn, context)
    update_remove_btn.effective_message.reply_text.assert_awaited_once()
    assert update_remove_btn.effective_message.reply_text.call_args.kwargs["text"] == WISHLIST_REMOVE_PROMPT
