"""Unit tests for Markdown validation, entity escaping on deserialization, and description markup."""

import pytest
from bot.participants.participant import Participant
from bot.recommendations.book import Book
from bot.recommendations.category import RecommendationCategory
from bot.timetable.event import Event
from bot.timetable.markdown_validator import MarkdownValidator
from admin.services.timetable_service import AdminTimetableService
from admin.server.router import AdminRouter
from admin.server.request import AdminRequest


def test_markdown_validator_valid():
    assert MarkdownValidator.validate("") is True
    assert MarkdownValidator.validate("Простой текст без разметки") is True
    assert MarkdownValidator.validate("*Жирный текст* и _курсив_") is True
    assert MarkdownValidator.validate("Текст с `кодом` и ```блоком\nкода```") is True
    assert MarkdownValidator.validate("Ссылка [Сайт фестиваля](https://example.com)") is True
    assert MarkdownValidator.validate("Экранированный символ: \\_подчеркивание\\_ и \\*звездочка\\*") is True


def test_markdown_validator_invalid():
    with pytest.raises(ValueError, match="незакрытый"):
        MarkdownValidator.validate("Текст с *незакрытой звездочкой")

    with pytest.raises(ValueError, match="незакрытый"):
        MarkdownValidator.validate("Текст с _незакрытым подчеркиванием")

    with pytest.raises(ValueError, match="незакрытый"):
        MarkdownValidator.validate("Текст с `незакрытым кодом")

    with pytest.raises(ValueError, match="незакрытый"):
        MarkdownValidator.validate("Текст с ```незакрытым блоком")

    with pytest.raises(ValueError, match="незакрытая ссылка|незакрытая скобка"):
        MarkdownValidator.validate("Текст с [битой ссылкой")

    with pytest.raises(ValueError, match="символ экранирования"):
        MarkdownValidator.validate("Строка с экранированием в конце\\")


def test_event_deserialization_and_formatting_markup_false():
    data = {
        "time": "12:00_pm*",
        "title": "Title with *stars* and _underscores_",
        "location": "Location_1 [hall]",
        "organizer": "Bohemian_mom & Prague*Tower",
        "participants": ["Author_1", "Author*2"],
        "description": "Description with *unclosed and _unclosed",
        "description_markup": False,
    }
    # Deserialization must keep raw unescaped values
    event = Event.from_dict(data)

    assert event.time == "12:00_pm*"
    assert event.title == "Title with *stars* and _underscores_"
    assert event.location == "Location_1 [hall]"
    assert event.organizer == "Bohemian_mom & Prague*Tower"
    assert event.participants == ["Author_1", "Author*2"]
    assert event.description == "Description with *unclosed and _unclosed"
    assert event.description_markup is False

    # Formatting into Markdown must escape special characters
    formatted = event.format_markdown()
    assert "⌚ *12:00\\_pm\\** — *Title with \\*stars\\* and \\_underscores\\_*" in formatted
    assert "📖 *Организатор:* Bohemian\\_mom & Prague\\*Tower" in formatted
    assert "👥 *Участники:* Author\\_1, Author\\*2" in formatted
    assert "📝 Description with \\*unclosed and \\_unclosed" in formatted
    assert event.to_markdown() == formatted


def test_event_deserialization_and_formatting_markup_true():
    data = {
        "time": "12:00",
        "title": "Title with _underscores_",
        "location": "Location_1",
        "organizer": "Bohemian_mom",
        "participants": ["Author_1"],
        "description": "Description with *valid bold* and [link](https://example.com)",
        "description_markup": True,
    }
    event = Event.from_dict(data)

    # Raw values stored
    assert event.title == "Title with _underscores_"
    assert event.organizer == "Bohemian_mom"
    assert event.description == "Description with *valid bold* and [link](https://example.com)"
    assert event.description_markup is True

    # Formatting: title and organizer escaped, description preserved
    formatted = event.format_markdown()
    assert "Title with \\_underscores\\_" in formatted
    assert "Bohemian\\_mom" in formatted
    assert "📝 Description with *valid bold* and [link](https://example.com)" in formatted
    assert event.to_markdown() == formatted


def test_participant_deserialization_and_formatting():
    data = {
        "name": "Издательство _Звезда_*",
        "stand": "Стенд [12_A]",
        "description": "Описание *тест* _тест_",
        "link": "https://example.com/page_1",
    }
    # Deserialization leaves raw strings intact
    p = Participant.from_dict(data)
    assert p.name == "Издательство _Звезда_*"
    assert p.stand == "Стенд [12_A]"
    assert p.description == "Описание *тест* _тест_"
    assert p.link == "https://example.com/page_1"

    # Button label must NOT contain backslashes / escape characters
    btn_label = p.format_button_label()
    assert btn_label == "📍 Стенд Стенд [12_A] — Издательство _Звезда_*"
    assert "\\" not in btn_label

    # Markdown representation must escape
    md = p.format_markdown()
    assert "👥 *Издательство \\_Звезда\\_\\**" in md
    assert "📍 *Стенд:* Стенд \\[12\\_A]" in md
    assert "📝 Описание \\*тест\\* \\_тест\\_" in md
    assert "🔗 *Ссылка:* https://example.com/page\\_1" in md
    assert p.to_markdown() == md


def test_book_and_category_deserialization_and_formatting():
    book_data = {
        "title": "Книга *1* _тест_",
        "authors": ["Автор_1", "Автор*2"],
        "soldBy": ["Стенд_1"],
        "description": "Описание _книги_",
    }
    category_data = {
        "rec": "Категория *Лучшее* _2026_",
        "emoji": "⭐",
        "books": [book_data],
    }

    cat = RecommendationCategory.from_dict(category_data)
    # Raw values in models
    assert cat.name == "Категория *Лучшее* _2026_"
    assert cat.books[0].title == "Книга *1* _тест_"
    assert cat.books[0].authors == ["Автор_1", "Автор*2"]
    assert cat.books[0].sold_by == ["Стенд_1"]

    # Formatted Markdown
    book_md = cat.books[0].format_markdown()
    assert "📖 *Книга \\*1\\* \\_тест\\_*" in book_md
    assert "✍️ *Авторы:* Автор\\_1, Автор\\*2" in book_md
    assert "🏢 *Где купить:* Стенд\\_1" in book_md
    assert "📝 Описание \\_книги\\_" in book_md
    assert cat.books[0].to_markdown() == book_md

    cat_md = cat.format_markdown()
    assert "⭐ *Рекомендации: Категория \\*Лучшее\\* \\_2026\\_*" in cat_md
    assert cat.to_markdown() == cat_md


def test_admin_timetable_service_markup_validation(tmp_path):
    service = AdminTimetableService(directory_path=str(tmp_path))
    date_key = service.create_day("15092026")

    # Adding event with valid markup
    service.add_event(
        date=date_key,
        time="10:00",
        title="Valid Event",
        location="Hall 1",
        description="*Valid bold* and _italic_",
        description_markup=True,
    )

    day_dict = service.get_day_dict(date_key)
    assert len(day_dict["events"]) == 1
    assert day_dict["events"][0]["description_markup"] is True

    # Adding event with invalid markup when description_markup=True should fail
    with pytest.raises(ValueError, match="Некорректная разметка Markdown"):
        service.add_event(
            date=date_key,
            time="11:00",
            title="Invalid Event",
            location="Hall 1",
            description="*Unclosed bold",
            description_markup=True,
        )

    # Adding event with invalid markup when description_markup=False should succeed
    service.add_event(
        date=date_key,
        time="11:00",
        title="Event with raw text",
        location="Hall 1",
        description="*Unclosed bold is fine in plain text",
        description_markup=False,
    )
    day_dict = service.get_day_dict(date_key)
    assert len(day_dict["events"]) == 2


def test_admin_broadcast_markup_validation():
    router = AdminRouter()
    # Mock authentication
    router.session_manager.is_valid_session = lambda token: True

    # Post invalid broadcast form
    req_invalid = AdminRequest(
        method="POST",
        path="/broadcast/send",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"text=Hello+*unclosed+bold",
    )
    res_invalid = router.route(req_invalid)
    assert res_invalid.status_code == 302
    assert "error=" in res_invalid.headers.get("Location", "")

    # Post invalid API broadcast
    req_api_invalid = AdminRequest(
        method="POST",
        path="/api/broadcast/send",
        headers={"content-type": "application/json"},
        body=b'{"text": "Hello *unclosed bold", "parse_mode": "Markdown"}',
    )
    res_api_invalid = router.route(req_api_invalid)
    assert res_api_invalid.status_code == 400


def test_timetable_service_and_wishlist_markdown_escaping(tmp_path):
    import json
    from bot.timetable.service import TimetableService
    from bot.wishlist.book import Book as WishlistBook

    # Test TimetableService format_timetable with special characters in location and event
    file_path = tmp_path / "12092026.json"
    file_path.write_text(json.dumps({
        "date": "12092026",
        "events": [
            {
                "time": "12:00",
                "title": "Discussion *PBT*",
                "location": "Stage_1 [main]",
                "organizer": "Bohemian_mom",
                "description": "Raw _description_ here",
                "description_markup": False,
                "is_master_class": True,
            }
        ]
    }, ensure_ascii=False), encoding="utf-8")

    tt_service = TimetableService(timetables_dir=str(tmp_path))
    formatted = tt_service.format_timetable("12092026", "Stage_1 [main]")
    assert "📍 *Площадка:* Stage\\_1 \\[main]" in formatted
    assert "Bohemian\\_mom" in formatted
    assert "Raw \\_description\\_ here" in formatted

    # Test master class details formatting
    event = tt_service.get_day("12092026").events[0]
    mc_formatted = tt_service.format_master_class_details("12092026", event)
    assert "🎨 *Мастер-класс: Discussion \\*PBT\\**" in mc_formatted
    assert "📍 *Площадка:* Stage\\_1 \\[main]" in mc_formatted
    assert "📖 *Организатор:* Bohemian\\_mom" in mc_formatted
    assert "Raw \\_description\\_ here" in mc_formatted

    # Test WishlistBook format_entry
    wb = WishlistBook(
        title="Book_with_underscores*",
        authors="Author_1 & Author*2",
        publishing="Pub_House",
        isbn="978-3-16-148410-0",
        user_notes="My_note*",
    )
    wb_md = wb.format_entry(index=1)
    assert "1. *«Book\\_with\\_underscores\\*»*" in wb_md
    assert "— Author\\_1 & Author\\*2" in wb_md
    assert "Изд: Pub\\_House" in wb_md
    assert "ISBN: 978-3-16-148410-0" in wb_md
    assert "_Заметка: My\\_note\\*_" in wb_md
    assert wb.to_markdown(index=1) == wb_md
