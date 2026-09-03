"""Unit tests for Recommendations models, service, keyboards, and section."""

import json
from unittest.mock import AsyncMock, MagicMock
import pytest

from bot.content import RECOMMENDATIONS_MESSAGE
from bot.keyboards import CB_RECOMMENDATIONS
from bot.recommendations.book import Book
from bot.recommendations.category import RecommendationCategory
from bot.recommendations.keyboards import (
    CB_REC_CATEGORY_PREFIX,
    CB_RECS_CATEGORIES,
    get_categories_inline_keyboard,
    get_recommendation_details_keyboard,
)
from bot.recommendations.service import RecommendationsService
from bot.sections.recommendations import Recommendations


def test_book_from_dict_and_format():
    data = {
        "title": "Книга Жопова",
        "description": "Новая книга Жопова о том, как писать книги.",
        "authors": ["Вася Жопов", "Маша Жопова"],
        "soldBy": ["Издательство 123", "Книжный магазин 456"],
    }
    book = Book.from_dict(data)
    assert book.title == "Книга Жопова"
    assert book.description == "Новая книга Жопова о том, как писать книги."
    assert book.authors == ["Вася Жопов", "Маша Жопова"]
    assert book.sold_by == ["Издательство 123", "Книжный магазин 456"]

    md = book.format_markdown()
    assert "📖 *Книга Жопова*" in md
    assert "📝 Новая книга Жопова о том, как писать книги." in md
    assert "✍️ *Авторы:* Вася Жопов, Маша Жопова" in md
    assert "🏢 *Где купить:* Издательство 123, Книжный магазин 456" in md


def test_book_single_author():
    data = {
        "title": "Сказки",
        "description": "Описание сказок.",
        "authors": "Вася Жопов",
        "sold_by": "Издательство 1488",
    }
    book = Book.from_dict(data)
    assert book.authors == ["Вася Жопов"]
    assert book.sold_by == ["Издательство 1488"]

    md = book.format_markdown()
    assert "✍️ *Автор:* Вася Жопов" in md
    assert "🏢 *Где купить:* Издательство 1488" in md


def test_recommendation_category_from_dict_and_format():
    data = {
        "rec": "Для детей",
        "books": [
            {
                "title": "Сказки Жопова",
                "description": "Сказки для детей.",
                "authors": ["Вася Жопов"],
                "soldBy": ["Издательство 1488"],
            }
        ],
    }
    category = RecommendationCategory.from_dict(data)
    assert category.name == "Для детей"
    assert len(category.books) == 1
    assert category.books[0].title == "Сказки Жопова"

    md = category.format_markdown()
    assert "📚 *Рекомендации: Для детей*" in md
    assert "📖 *Сказки Жопова*" in md


def test_recommendation_service_with_real_assets():
    service = RecommendationsService()
    categories = service.get_category_names()
    assert "Нонфикшн" in categories
    assert "Для детей" in categories

    cat_nonfiction = service.get_category("Нонфикшн")
    assert cat_nonfiction is not None
    assert len(cat_nonfiction.books) >= 2
    titles = [b.title for b in cat_nonfiction.books]
    assert "Книга Жопова" in titles
    assert "Книга Нежопова" in titles

    formatted = service.format_category_recommendations("Нонфикшн")
    assert "📚 *Рекомендации: Нонфикшн*" in formatted
    assert "Книга Жопова" in formatted
    assert "Книга Нежопова" in formatted


def test_recommendation_keyboards():
    categories = ["Нонфикшн", "Для детей"]
    kb = get_categories_inline_keyboard(categories)
    assert len(kb.inline_keyboard) == 2
    assert kb.inline_keyboard[0][0].text == "📚 Нонфикшн"
    assert kb.inline_keyboard[0][0].callback_data == f"{CB_REC_CATEGORY_PREFIX}0"
    assert kb.inline_keyboard[1][0].text == "📚 Для детей"
    assert kb.inline_keyboard[1][0].callback_data == f"{CB_REC_CATEGORY_PREFIX}1"

    details_kb = get_recommendation_details_keyboard()
    assert len(details_kb.inline_keyboard) == 1
    assert details_kb.inline_keyboard[0][0].callback_data == CB_RECOMMENDATIONS


@pytest.mark.asyncio
async def test_recommendations_section_callbacks():
    recs = Recommendations()
    assert recs.matches_callback(CB_RECOMMENDATIONS)
    assert recs.matches_callback(CB_RECS_CATEGORIES)
    assert recs.matches_callback(f"{CB_REC_CATEGORY_PREFIX}Нонфикшн")
    assert not recs.matches_callback("unknown_cb")

    # 1. Initial callback -> show categories
    query = AsyncMock()
    query.data = CB_RECOMMENDATIONS
    query.edit_message_text = AsyncMock()

    await recs.handle_callback_query(query)
    query.edit_message_text.assert_awaited_once()
    assert query.edit_message_text.call_args.kwargs["text"] == RECOMMENDATIONS_MESSAGE

    # 2. Category callback -> show books
    query_books = AsyncMock()
    query_books.data = f"{CB_REC_CATEGORY_PREFIX}Нонфикшн"
    query_books.edit_message_text = AsyncMock()

    await recs.handle_callback_query(query_books)
    query_books.edit_message_text.assert_awaited_once()
    books_text = query_books.edit_message_text.call_args.kwargs["text"]
    assert "Нонфикшн" in books_text
    assert "Книга Жопова" in books_text


def test_recommendations_service_reload_on_each_request(tmp_path):
    file_path = tmp_path / "recs.json"
    file_path.write_text(
        json.dumps({
            "recs": [
                {
                    "rec": "Категория 1",
                    "books": [
                        {
                            "title": "Книга 1",
                            "authors": ["Автор 1"],
                        }
                    ],
                }
            ]
        }),
        encoding="utf-8",
    )

    service = RecommendationsService(file_path=str(file_path))
    cats = service.get_category_names()
    assert cats == ["Категория 1"]
    cat = service.get_category("Категория 1")
    assert cat.books[0].title == "Книга 1"

    # Update file content on disk without recreating service
    file_path.write_text(
        json.dumps({
            "recs": [
                {
                    "rec": "Категория 1",
                    "books": [
                        {
                            "title": "Книга Обновленная",
                            "authors": ["Автор 1"],
                        }
                    ],
                },
                {
                    "rec": "Новая Категория 2",
                    "books": [
                        {
                            "title": "Книга 2",
                            "authors": ["Автор 2"],
                        }
                    ],
                },
            ]
        }),
        encoding="utf-8",
    )

    # Next call must immediately reflect changes
    updated_cats = service.get_category_names()
    assert updated_cats == ["Категория 1", "Новая Категория 2"]

    updated_cat = service.get_category("Категория 1")
    assert updated_cat.books[0].title == "Книга Обновленная"


def test_recommendations_one_class_per_module_imports():
    from bot.recommendations import Book as PackageBook
    from bot.recommendations import RecommendationCategory as PackageCategory
    from bot.recommendations import RecommendationsService as PackageService
    from bot.recommendations.book import Book as DirectBook
    from bot.recommendations.category import RecommendationCategory as DirectCategory
    from bot.recommendations.service import RecommendationsService as DirectService

    assert PackageBook is DirectBook
    assert PackageCategory is DirectCategory
    assert PackageService is DirectService


@pytest.mark.asyncio
async def test_long_recommendation_category_name_callback_under_64_bytes():
    """Ensure dynamic recommendation category keyboards do not exceed Telegram's 64-byte limit."""
    long_cat = "Очень длинная категория художественной и документальной литературы с описаниями"
    assert len(f"rec_cat:{long_cat}".encode("utf-8")) > 64

    kb = get_categories_inline_keyboard([long_cat])
    for row in kb.inline_keyboard:
        for btn in row:
            assert len(btn.callback_data.encode("utf-8")) <= 64

    service = RecommendationsService()
    recs = Recommendations(service=service)
    service.get_categories = lambda: [RecommendationCategory(name=long_cat, emoji="📚", books=[])]

    query = AsyncMock()
    query.data = kb.inline_keyboard[0][0].callback_data  # "rec_cat:0"
    query.edit_message_text = AsyncMock()

    await recs.handle_callback_query(query)
    query.edit_message_text.assert_awaited_once()
    assert long_cat in query.edit_message_text.call_args.kwargs["text"]
