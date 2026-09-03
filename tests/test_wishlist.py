"""Tests for user wishlist database, service, keyboards, section, and bot handlers."""

import io
import os
import sqlite3
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
import pytest
from telegram import Update
from telegram.constants import ParseMode
import zxingcpp

from bot.content import (
    BTN_WISHLIST,
    BTN_WISHLIST_ADD,
    BTN_WISHLIST_ADD_ISBN,
    BTN_WISHLIST_ADD_NOTE,
    BTN_WISHLIST_CANCEL,
    BTN_WISHLIST_CONFIRM,
    BTN_WISHLIST_EDIT,
    BTN_WISHLIST_GET,
    BTN_WISHLIST_REMOVE,
    BUTTON_CALLBACK_MAP,
    CB_WISHLIST,
    CB_WISHLIST_ADD,
    CB_WISHLIST_ADD_ISBN,
    CB_WISHLIST_EDIT,
    CB_WISHLIST_GET,
    CB_WISHLIST_REMOVE,
    CB_WL_CANCEL_ISBN,
    CB_WL_CONFIRM_ISBN,
    WISHLIST_ADD_PROMPT,
    WISHLIST_BARCODE_NOT_FOUND_MESSAGE,
    WISHLIST_EDIT_PROMPT,
    WISHLIST_EMPTY_MESSAGE,
    WISHLIST_ISBN_INVALID_MESSAGE,
    WISHLIST_ISBN_NOT_FOUND_MESSAGE,
    WISHLIST_ISBN_PROMPT,
    WISHLIST_MESSAGE,
    WISHLIST_PHOTO_TOO_LARGE_MESSAGE,
    WISHLIST_REMOVE_PROMPT,
)
from bot.handlers import (
    button_callback_handler,
    photo_message_handler,
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
from bot.wishlist.isbn import clean_isbn, decode_barcode_from_image, lookup_book_by_isbn
from bot.wishlist.keyboards import (
    BOOK_ATTRIBUTES,
    CB_WL_EDIT_ATTR_PREFIX,
    CB_WL_EDIT_BOOK_PREFIX,
    CB_WL_REMOVE_BOOK_PREFIX,
    WISHLIST_CALLBACK_MAP,
    get_book_added_inline_keyboard,
    get_book_attributes_inline_keyboard,
    get_isbn_confirm_inline_keyboard,
    get_isbn_input_inline_keyboard,
    get_wishlist_add_inline_keyboard,
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


# ==============================================================================
# ISBN, Barcode, and Flow Tests
# ==============================================================================

def test_clean_isbn():
    assert clean_isbn("978-0-14-044913-6") == "9780140449136"
    assert clean_isbn("978 0 14 044913 6") == "9780140449136"
    assert clean_isbn("0-14-044913-2") == "0140449132"
    assert clean_isbn("043942089X") == "043942089X"
    assert clean_isbn("ISBN 978-0-14-044913-6 (pbk.)") == "9780140449136"
    assert clean_isbn("") is None
    assert clean_isbn("not-an-isbn") is None
    assert clean_isbn(None) is None


def test_decode_barcode_from_image():
    # 1. Create a real EAN-13 barcode image
    bc = zxingcpp.create_barcode("9780140449136", zxingcpp.BarcodeFormat.EAN13)
    img = zxingcpp.write_barcode_to_image(bc)
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        # Convert zxingcpp image to PIL
        pil_img = Image.frombuffer("L", (img.shape[1], img.shape[0]), bytes(img))
        pil_img.save(tmp_path, format="PNG")
        
        decoded = decode_barcode_from_image(tmp_path)
        assert decoded == "9780140449136"
        
        # Test bytes
        with open(tmp_path, "rb") as f:
            raw_bytes = f.read()
        assert decode_barcode_from_image(raw_bytes) == "9780140449136"
        
        # Test PIL Image
        assert decode_barcode_from_image(pil_img) == "9780140449136"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # 2. Blank image -> None
    blank_img = Image.new("RGB", (200, 200), color="white")
    assert decode_barcode_from_image(blank_img) is None

    # 3. Invalid source -> None
    assert decode_barcode_from_image("non_existent_path.png") is None
    assert decode_barcode_from_image(b"invalid data") is None


def test_lookup_book_by_isbn_open_library():
    mock_meta = {
        "ISBN-13": "9780140449136",
        "Title": "Crime and punishment",
        "Authors": ["Fyodor Dostoyevsky"],
        "Publisher": "Penguin",
        "Year": "2003",
        "Language": "",
    }
    with patch("isbnlib.meta", return_value=mock_meta):
        book = lookup_book_by_isbn("978-0-14-044913-6")
        assert book is not None
        assert book.title == "Crime and punishment"
        assert book.authors == "Fyodor Dostoyevsky"
        assert book.publishing == "Penguin"
        assert book.year == 2003
        assert book.isbn == "9780140449136"


def test_lookup_book_by_isbn_fallback():
    mock_meta_goob = {
        "ISBN-13": "9780132350884",
        "Title": "Clean Code",
        "Authors": ["Robert C. Martin"],
        "Publisher": "Prentice Hall",
        "Year": "2008",
    }

    def side_effect(isbn, service=None):
        if service == "openl":
            return {}
        if service == "goob":
            return mock_meta_goob
        return {}

    with patch("isbnlib.meta", side_effect=side_effect):
        book = lookup_book_by_isbn("9780132350884")
        assert book is not None
        assert book.title == "Clean Code"
        assert book.authors == "Robert C. Martin"
        assert book.publishing == "Prentice Hall"
        assert book.year == 2008
        assert book.isbn == "9780132350884"


def test_lookup_book_by_isbn_not_found():
    with patch("isbnlib.meta", return_value={}):
        assert lookup_book_by_isbn("9780000000000") is None
    assert lookup_book_by_isbn("invalid") is None


def test_isbn_keyboards():
    add_kb = get_wishlist_add_inline_keyboard()
    add_cbs = [b.callback_data for row in add_kb.inline_keyboard for b in row]
    assert CB_WISHLIST_ADD_ISBN in add_cbs
    assert CB_WISHLIST in add_cbs

    input_kb = get_isbn_input_inline_keyboard()
    input_cbs = [b.callback_data for row in input_kb.inline_keyboard for b in row]
    assert CB_WISHLIST_ADD in input_cbs
    assert CB_WISHLIST in input_cbs

    confirm_kb = get_isbn_confirm_inline_keyboard()
    confirm_cbs = [b.callback_data for row in confirm_kb.inline_keyboard for b in row]
    assert CB_WL_CONFIRM_ISBN in confirm_cbs
    assert CB_WL_CANCEL_ISBN in confirm_cbs


@pytest.mark.asyncio
async def test_wishlist_add_flow_title_when_untapped(temp_service):
    """If 'By ISBN' is NOT tapped, text message with title is accepted as before."""
    wishlist_section.service = temp_service
    context = MagicMock()
    context.user_data = {}

    # Step 1: User triggers Add Book
    query = MagicMock()
    query.data = CB_WISHLIST_ADD
    query.from_user = MagicMock(id=111222)
    query.edit_message_text = AsyncMock()
    await wishlist_section.handle_callback_query(query, context=context)

    assert context.user_data.get("awaiting_wishlist_title") is True
    assert context.user_data.get("awaiting_wishlist_isbn") is None

    # Step 2: User types title directly
    update_text = MagicMock(spec=Update)
    update_text.effective_message = AsyncMock(text="Dune")
    update_text.effective_user = MagicMock(id=111222)
    await text_message_handler(update_text, context)

    assert context.user_data.get("awaiting_wishlist_title") is False
    user_id = get_user_id(111222)
    books = temp_service.get_wishlist(user_id)
    assert len(books) == 1
    assert books[0].title == "Dune"


@pytest.mark.asyncio
async def test_wishlist_add_flow_by_isbn_text_success_and_confirm(temp_service):
    """If 'By ISBN' is tapped and valid ISBN is sent, bot finds book and adds upon confirmation."""
    wishlist_section.service = temp_service
    context = MagicMock()
    context.user_data = {}

    # Step 1: Tap "By ISBN"
    query = MagicMock()
    query.data = CB_WISHLIST_ADD_ISBN
    query.from_user = MagicMock(id=555666)
    query.edit_message_text = AsyncMock()
    await wishlist_section.handle_callback_query(query, context=context)

    assert context.user_data.get("awaiting_wishlist_isbn") is True
    assert context.user_data.get("awaiting_wishlist_title") is None

    # Step 2: Send ISBN text
    found_book = Book(title="1984", authors="George Orwell", publishing="Secker & Warburg", isbn="9780451524935", year=1949)
    with patch("bot.handlers.lookup_book_by_isbn", return_value=found_book):
        update_isbn = MagicMock(spec=Update)
        update_isbn.effective_message = AsyncMock(text="978-0451524935")
        update_isbn.effective_user = MagicMock(id=555666)
        await text_message_handler(update_isbn, context)

    assert context.user_data.get("pending_isbn_book") == found_book
    assert context.user_data.get("awaiting_wishlist_isbn") is None
    # Verify book is NOT added to DB yet
    user_id = get_user_id(555666)
    assert len(temp_service.get_wishlist(user_id)) == 0
    # Verify confirmation markup
    reply_markup = update_isbn.effective_message.reply_text.call_args.kwargs["reply_markup"]
    confirm_cbs = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
    assert CB_WL_CONFIRM_ISBN in confirm_cbs

    # Step 3: User confirms addition
    query_confirm = MagicMock()
    query_confirm.data = CB_WL_CONFIRM_ISBN
    query_confirm.from_user = MagicMock(id=555666)
    query_confirm.edit_message_text = AsyncMock()
    await wishlist_section.handle_callback_query(query_confirm, context=context)

    # Now it is added to the database
    books = temp_service.get_wishlist(user_id)
    assert len(books) == 1
    assert books[0].title == "1984"
    assert books[0].authors == "George Orwell"
    assert books[0].year == 1949


@pytest.mark.asyncio
async def test_wishlist_add_flow_by_isbn_text_cancel(temp_service):
    """If user cancels confirmation, book is not added."""
    wishlist_section.service = temp_service
    context = MagicMock()
    found_book = Book(title="Fahrenheit 451", authors="Ray Bradbury", isbn="9781451673319")
    context.user_data = {"pending_isbn_book": found_book}

    query_cancel = MagicMock()
    query_cancel.data = CB_WL_CANCEL_ISBN
    query_cancel.from_user = MagicMock(id=777888)
    query_cancel.edit_message_text = AsyncMock()
    await wishlist_section.handle_callback_query(query_cancel, context=context)

    user_id = get_user_id(777888)
    assert len(temp_service.get_wishlist(user_id)) == 0
    assert context.user_data.get("pending_isbn_book") is None


@pytest.mark.asyncio
async def test_wishlist_add_flow_by_isbn_not_found(temp_service):
    """If book is not found by ISBN, user is informed and returns to add book menu."""
    wishlist_section.service = temp_service
    context = MagicMock()
    context.user_data = {"awaiting_wishlist_isbn": True}

    with patch("bot.handlers.lookup_book_by_isbn", return_value=None):
        update_isbn = MagicMock(spec=Update)
        update_isbn.effective_message = AsyncMock(text="9780000000002")
        update_isbn.effective_user = MagicMock(id=999000)
        await text_message_handler(update_isbn, context)

    assert context.user_data.get("awaiting_wishlist_isbn") is None
    assert context.user_data.get("awaiting_wishlist_title") is True
    reply_text = update_isbn.effective_message.reply_text.call_args.kwargs["text"]
    assert "не найдена" in reply_text
    reply_markup = update_isbn.effective_message.reply_text.call_args.kwargs["reply_markup"]
    add_cbs = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
    assert CB_WISHLIST_ADD_ISBN in add_cbs


@pytest.mark.asyncio
async def test_wishlist_add_flow_by_isbn_invalid_text(temp_service):
    """If invalid text is sent during ISBN awaiting, user is warned and stays in ISBN input."""
    wishlist_section.service = temp_service
    context = MagicMock()
    context.user_data = {"awaiting_wishlist_isbn": True}

    update_invalid = MagicMock(spec=Update)
    update_invalid.effective_message = AsyncMock(text="hello_world_not_isbn")
    update_invalid.effective_user = MagicMock(id=999000)
    await text_message_handler(update_invalid, context)

    assert context.user_data.get("awaiting_wishlist_isbn") is True
    reply_text = update_invalid.effective_message.reply_text.call_args.kwargs["text"]
    assert reply_text == WISHLIST_ISBN_INVALID_MESSAGE
    reply_markup = update_invalid.effective_message.reply_text.call_args.kwargs["reply_markup"]
    cbs = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
    assert CB_WISHLIST_ADD in cbs


@pytest.mark.asyncio
async def test_wishlist_photo_barcode_success(temp_service):
    """Photo with barcode reads barcode in-memory and presents confirmation."""
    wishlist_section.service = temp_service
    context = MagicMock()
    context.user_data = {"awaiting_wishlist_isbn": True}

    # Create dummy image in memory
    img_byte_arr = io.BytesIO()
    Image.new("RGB", (100, 100), color="white").save(img_byte_arr, format="PNG")
    dummy_bytes = bytearray(img_byte_arr.getvalue())

    mock_file = MagicMock()
    mock_file.file_size = len(dummy_bytes)
    mock_file.download_as_bytearray = AsyncMock(return_value=dummy_bytes)
    context.bot.get_file = AsyncMock(return_value=mock_file)

    found_book = Book(title="The Hobbit", authors="J.R.R. Tolkien", isbn="9780261102217")

    with patch("bot.handlers.decode_barcode_from_image", return_value="9780261102217"), \
         patch("bot.handlers.lookup_book_by_isbn", return_value=found_book):
        update_photo = MagicMock(spec=Update)
        photo_mock = MagicMock(file_id="photo_123", file_size=len(dummy_bytes))
        update_photo.effective_message = AsyncMock(photo=[photo_mock])
        update_photo.effective_user = MagicMock(id=123123)
        await photo_message_handler(update_photo, context)

    # Verify pending book set and confirmation asked
    assert context.user_data.get("pending_isbn_book") == found_book
    assert "The Hobbit" in update_photo.effective_message.reply_text.call_args.kwargs["text"]
    reply_markup = update_photo.effective_message.reply_text.call_args.kwargs["reply_markup"]
    confirm_cbs = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
    assert CB_WL_CONFIRM_ISBN in confirm_cbs


@pytest.mark.asyncio
async def test_wishlist_photo_barcode_not_detected(temp_service):
    """Photo without barcode warns user and stays in By ISBN input."""
    wishlist_section.service = temp_service
    context = MagicMock()
    context.user_data = {"awaiting_wishlist_isbn": True}

    img_byte_arr = io.BytesIO()
    Image.new("RGB", (50, 50), color="white").save(img_byte_arr, format="PNG")
    dummy_bytes = bytearray(img_byte_arr.getvalue())

    mock_file = MagicMock()
    mock_file.file_size = len(dummy_bytes)
    mock_file.download_as_bytearray = AsyncMock(return_value=dummy_bytes)
    context.bot.get_file = AsyncMock(return_value=mock_file)

    with patch("bot.handlers.decode_barcode_from_image", return_value=None):
        update_photo = MagicMock(spec=Update)
        photo_mock = MagicMock(file_id="photo_456", file_size=len(dummy_bytes))
        update_photo.effective_message = AsyncMock(photo=[photo_mock])
        update_photo.effective_user = MagicMock(id=123123)
        await photo_message_handler(update_photo, context)

    # Verify warning and returned to ISBN input
    assert context.user_data.get("awaiting_wishlist_isbn") is True
    assert update_photo.effective_message.reply_text.call_args.kwargs["text"] == WISHLIST_BARCODE_NOT_FOUND_MESSAGE
    reply_markup = update_photo.effective_message.reply_text.call_args.kwargs["reply_markup"]
    cbs = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
    assert CB_WISHLIST_ADD in cbs


@pytest.mark.asyncio
async def test_wishlist_photo_too_large_rejected_by_photo_size(temp_service):
    """Photos exceeding 15MB are denied with an error message before downloading."""
    wishlist_section.service = temp_service
    context = MagicMock()
    context.user_data = {"awaiting_wishlist_isbn": True}

    update_photo = MagicMock(spec=Update)
    photo_mock = MagicMock(file_id="photo_huge", file_size=16 * 1024 * 1024)
    update_photo.effective_message = AsyncMock(photo=[photo_mock])
    update_photo.effective_user = MagicMock(id=123123)

    await photo_message_handler(update_photo, context)

    assert context.bot.get_file.call_count == 0
    assert context.user_data.get("awaiting_wishlist_isbn") is True
    assert update_photo.effective_message.reply_text.call_args.kwargs["text"] == WISHLIST_PHOTO_TOO_LARGE_MESSAGE


@pytest.mark.asyncio
async def test_wishlist_photo_too_large_rejected_by_file_size(temp_service):
    """Files exceeding 15MB reported by Telegram File object are denied before bytearray conversion."""
    wishlist_section.service = temp_service
    context = MagicMock()
    context.user_data = {"awaiting_wishlist_isbn": True}

    mock_file = MagicMock()
    mock_file.file_size = 16 * 1024 * 1024
    mock_file.download_as_bytearray = AsyncMock()
    context.bot.get_file = AsyncMock(return_value=mock_file)

    update_photo = MagicMock(spec=Update)
    photo_mock = MagicMock(file_id="photo_large_file", file_size=None)
    update_photo.effective_message = AsyncMock(photo=[photo_mock])
    update_photo.effective_user = MagicMock(id=123123)

    await photo_message_handler(update_photo, context)

    assert mock_file.download_as_bytearray.call_count == 0
    assert context.user_data.get("awaiting_wishlist_isbn") is True
    assert update_photo.effective_message.reply_text.call_args.kwargs["text"] == WISHLIST_PHOTO_TOO_LARGE_MESSAGE


@pytest.mark.asyncio
async def test_wishlist_photo_too_large_rejected_by_downloaded_bytes(temp_service):
    """Downloaded bytearrays exceeding 15MB are denied with an appropriate error message."""
    wishlist_section.service = temp_service
    context = MagicMock()
    context.user_data = {"awaiting_wishlist_isbn": True}

    huge_bytes = bytearray(b"0" * (16 * 1024 * 1024))
    mock_file = MagicMock()
    mock_file.file_size = None
    mock_file.download_as_bytearray = AsyncMock(return_value=huge_bytes)
    context.bot.get_file = AsyncMock(return_value=mock_file)

    update_photo = MagicMock(spec=Update)
    photo_mock = MagicMock(file_id="photo_download_large", file_size=None)
    update_photo.effective_message = AsyncMock(photo=[photo_mock])
    update_photo.effective_user = MagicMock(id=123123)

    await photo_message_handler(update_photo, context)

    assert context.user_data.get("awaiting_wishlist_isbn") is True
    assert update_photo.effective_message.reply_text.call_args.kwargs["text"] == WISHLIST_PHOTO_TOO_LARGE_MESSAGE


def test_get_book_added_inline_keyboard():
    """Verify get_book_added_inline_keyboard includes note adding option and menu return."""
    markup = get_book_added_inline_keyboard(42)
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    callbacks = [btn.callback_data for btn in buttons]
    texts = [btn.text for btn in buttons]

    assert "wl_ed_a:42:user_notes" in callbacks
    assert CB_WISHLIST in callbacks
    assert BTN_WISHLIST_ADD_NOTE in texts


@pytest.mark.asyncio
async def test_wishlist_add_title_and_offer_notes_flow(temp_service):
    """After adding a book by title, bot offers to add notes and lets user write a note."""
    wishlist_section.service = temp_service
    context = MagicMock()
    context.user_data = {"awaiting_wishlist_title": True}

    # Step 1: User sends book title
    update_title = MagicMock(spec=Update)
    update_title.effective_message = AsyncMock(text="Гарри Поттер и Философский камень")
    update_title.effective_user = MagicMock(id=888999)
    await text_message_handler(update_title, context)

    user_id = get_user_id(888999)
    books = temp_service.get_wishlist(user_id)
    assert len(books) == 1
    added_book = books[0]
    assert added_book.title == "Гарри Поттер и Философский камень"

    # Verify markup has add note button for the added book
    reply_markup = update_title.effective_message.reply_text.call_args.kwargs["reply_markup"]
    cbs = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
    assert f"wl_ed_a:{added_book.id}:user_notes" in cbs

    # Step 2: User clicks "Add note"
    query_note = MagicMock()
    query_note.data = f"wl_ed_a:{added_book.id}:user_notes"
    query_note.from_user = MagicMock(id=888999)
    query_note.edit_message_text = AsyncMock()
    await wishlist_section.handle_callback_query(query_note, context=context)

    assert context.user_data.get("awaiting_wishlist_edit") == {
        "book_id": added_book.id,
        "attribute": "user_notes",
    }
    prompt_text = query_note.edit_message_text.call_args.kwargs["text"]
    assert "Заметка" in prompt_text

    # Step 3: User sends note text
    update_note = MagicMock(spec=Update)
    update_note.effective_message = AsyncMock(text="Купить иллюстрированное издание Росмэн")
    update_note.effective_user = MagicMock(id=888999)
    await text_message_handler(update_note, context)

    # Verify note updated in database
    updated = temp_service.get_book(user_id, added_book.id)
    assert updated.user_notes == "Купить иллюстрированное издание Росмэн"
    reply_text = update_note.effective_message.reply_text.call_args.kwargs["text"]
    assert "Купить иллюстрированное издание Росмэн" in reply_text


@pytest.mark.asyncio
async def test_wishlist_add_isbn_confirm_and_offer_notes_flow(temp_service):
    """After confirming ISBN book addition, bot offers to add notes."""
    wishlist_section.service = temp_service
    context = MagicMock()
    found_book = Book(title="Solaris", authors="Stanislaw Lem", isbn="9780156027601", year=1961)
    context.user_data = {"pending_isbn_book": found_book}

    query_confirm = MagicMock()
    query_confirm.data = CB_WL_CONFIRM_ISBN
    query_confirm.from_user = MagicMock(id=999888)
    query_confirm.edit_message_text = AsyncMock()
    await wishlist_section.handle_callback_query(query_confirm, context=context)

    user_id = get_user_id(999888)
    books = temp_service.get_wishlist(user_id)
    assert len(books) == 1
    added_book = books[0]
    assert added_book.title == "Solaris"

    # Verify confirmation markup offers note addition
    reply_markup = query_confirm.edit_message_text.call_args.kwargs["reply_markup"]
    cbs = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
    assert f"wl_ed_a:{added_book.id}:user_notes" in cbs
