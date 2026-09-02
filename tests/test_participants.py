"""Unit tests for Participants data models, service, keyboards, section, and admin service."""

import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram.constants import ParseMode

from bot.content import BTN_PARTICIPANTS, PARTICIPANTS_MESSAGE
from bot.keyboards import CB_PARTICIPANTS
from bot.participants.keyboards import (
    CB_PART_ITEM_PREFIX,
    CB_PARTICIPANTS_LIST,
    get_participant_details_keyboard,
    get_participants_inline_keyboard,
)
from bot.participants.participant import Participant
from bot.participants.service import ParticipantsService, sort_participant_key
from bot.sections.participants import Participants
from admin.services.participants_service import AdminParticipantsService


def test_participant_from_dict_and_formatting():
    data = {
        "name": "Издательство МИФ",
        "stand": "42",
        "description": "Книги по бизнесу и саморазвитию.",
        "link": "https://mif.ru",
    }
    part = Participant.from_dict(data)
    assert part.name == "Издательство МИФ"
    assert part.stand == "42"
    assert part.description == "Книги по бизнесу и саморазвитию."
    assert part.link == "https://mif.ru"

    btn_label = part.format_button_label()
    assert "42" in btn_label
    assert "Издательство МИФ" in btn_label

    md = part.format_markdown()
    assert "👥 *Издательство МИФ*" in md
    assert "📍 *Стенд:* 42" in md
    assert "📝 Книги по бизнесу и саморазвитию." in md
    assert "🔗 *Ссылка:* https://mif.ru" in md

    d = part.to_dict()
    assert d["name"] == "Издательство МИФ"
    assert d["stand"] == "42"

    # Participant without link and description
    minimal_part = Participant.from_dict({"name": "Автор", "stand": "7"})
    assert minimal_part.link == ""
    assert minimal_part.description == ""
    minimal_md = minimal_part.format_markdown()
    assert "👥 *Автор*" in minimal_md
    assert "📍 *Стенд:* 7" in minimal_md
    assert "🔗" not in minimal_md
    assert "📝" not in minimal_md


def test_participant_stand_sorting_numeric_before_alphanumeric():
    p_num10 = Participant(name="Десятый", stand="10")
    p_num2 = Participant(name="Второй", stand="2")
    p_num1 = Participant(name="Первый", stand="1")
    p_alpha_b = Participant(name="Бетта", stand="B-1")
    p_alpha_a2 = Participant(name="Альфа 2", stand="A-2")
    p_alpha_a1 = Participant(name="Альфа 1", stand="A-1")

    items = [p_num10, p_alpha_b, p_num2, p_alpha_a2, p_num1, p_alpha_a1]
    sorted_items = sorted(items, key=sort_participant_key)

    stands = [p.stand for p in sorted_items]
    assert stands == ["1", "2", "10", "A-1", "A-2", "B-1"]


def test_participants_service_with_file(tmp_path):
    file_path = tmp_path / "participants.json"
    file_path.write_text(
        json.dumps({
            "participants": [
                {
                    "name": "Второй стенд",
                    "stand": "2",
                    "description": "Описание 2",
                    "link": "https://two.com",
                },
                {
                    "name": "Первый стенд",
                    "stand": "1",
                    "description": "Описание 1",
                    "link": "https://one.com",
                },
                {
                    "name": "Стенд Зона А",
                    "stand": "Zone-A",
                    "description": "Описание А",
                    "link": "https://zone-a.com",
                },
            ]
        }),
        encoding="utf-8",
    )

    service = ParticipantsService(file_path=str(file_path))
    participants = service.get_participants()
    assert len(participants) == 3
    # Check sorted: 1, 2, Zone-A
    assert participants[0].stand == "1"
    assert participants[1].stand == "2"
    assert participants[2].stand == "Zone-A"

    # Get by index
    p0 = service.get_participant_by_index(0)
    assert p0 is not None
    assert p0.name == "Первый стенд"

    # Get by stand
    p_zone = service.get_participant("Zone-A")
    assert p_zone is not None
    assert p_zone.name == "Стенд Зона А"

    # Get by name
    p_name = service.get_participant("Второй стенд")
    assert p_name is not None
    assert p_name.stand == "2"

    # Format details
    details_md = service.format_participant_details("0")
    assert "Первый стенд" in details_md
    assert "📍 *Стенд:* 1" in details_md


def test_participants_keyboards():
    participants = [
        Participant(name="Альпина", stand="1"),
        Participant(name="МИФ", stand="2"),
    ]
    kb = get_participants_inline_keyboard(participants)
    assert len(kb.inline_keyboard) == 2
    assert "1" in kb.inline_keyboard[0][0].text
    assert "Альпина" in kb.inline_keyboard[0][0].text
    assert kb.inline_keyboard[0][0].callback_data == f"{CB_PART_ITEM_PREFIX}0"
    assert "2" in kb.inline_keyboard[1][0].text
    assert "МИФ" in kb.inline_keyboard[1][0].text
    assert kb.inline_keyboard[1][0].callback_data == f"{CB_PART_ITEM_PREFIX}1"

    details_kb = get_participant_details_keyboard()
    assert len(details_kb.inline_keyboard) == 1
    assert details_kb.inline_keyboard[0][0].callback_data == CB_PARTICIPANTS


@pytest.mark.asyncio
async def test_participants_section_flow(tmp_path):
    file_path = tmp_path / "participants.json"
    file_path.write_text(
        json.dumps({
            "participants": [
                {
                    "name": "Издательство",
                    "stand": "5",
                    "description": "Лучшие книги",
                    "link": "https://books.ru",
                }
            ]
        }),
        encoding="utf-8",
    )

    service = ParticipantsService(file_path=str(file_path))
    section = Participants(service=service)

    assert section.matches_callback(CB_PARTICIPANTS)
    assert section.matches_callback(CB_PARTICIPANTS_LIST)
    assert section.matches_callback(f"{CB_PART_ITEM_PREFIX}0")
    assert not section.matches_callback("random_cb")

    # 1. Send initial response
    msg = AsyncMock()
    msg.reply_text = AsyncMock()
    await section.send_response(msg)
    msg.reply_text.assert_awaited_once()
    assert msg.reply_text.call_args.kwargs["text"] == PARTICIPANTS_MESSAGE

    # 2. Callback -> details
    query_details = AsyncMock()
    query_details.data = f"{CB_PART_ITEM_PREFIX}0"
    query_details.edit_message_text = AsyncMock()
    await section.handle_callback_query(query_details)
    query_details.edit_message_text.assert_awaited_once()
    assert "Издательство" in query_details.edit_message_text.call_args.kwargs["text"]
    assert "5" in query_details.edit_message_text.call_args.kwargs["text"]

    # 3. Callback -> back to list
    query_back = AsyncMock()
    query_back.data = CB_PARTICIPANTS
    query_back.edit_message_text = AsyncMock()
    await section.handle_callback_query(query_back)
    query_back.edit_message_text.assert_awaited_once()
    assert query_back.edit_message_text.call_args.kwargs["text"] == PARTICIPANTS_MESSAGE


def test_admin_participants_service_crud_and_staging(tmp_path):
    file_path = tmp_path / "participants.json"
    admin_service = AdminParticipantsService(file_path=str(file_path))

    # Initial state empty
    assert len(admin_service.get_participants()) == 0
    assert not admin_service.has_pending_changes()

    # Add participant (staged)
    admin_service.add_participant(
        name="МИФ",
        stand="15",
        link="https://mif.ru",
        description="Книги",
    )
    assert admin_service.has_pending_changes()
    assert len(admin_service.get_participants()) == 1

    # Add another participant with numeric stand 2 -> should sort before 15
    admin_service.add_participant(
        name="Альпина",
        stand="2",
        link="https://alpinabook.ru",
    )
    parts = admin_service.get_participants()
    assert len(parts) == 2
    assert parts[0].name == "Альпина"
    assert parts[0].stand == "2"
    assert parts[1].name == "МИФ"
    assert parts[1].stand == "15"

    # Discard changes -> rolls back
    admin_service.discard_changes()
    assert not admin_service.has_pending_changes()
    assert len(admin_service.get_participants()) == 0

    # Add and commit
    admin_service.add_participant(name="Альпина", stand="2", link="https://alpina.ru")
    admin_service.add_participant(name="Самокат", stand="A-1", link="https://samokat.ru")
    admin_service.save_to_disk()
    assert not admin_service.has_pending_changes()

    # Reload fresh instance from disk
    fresh_service = AdminParticipantsService(file_path=str(file_path))
    loaded = fresh_service.get_participants()
    assert len(loaded) == 2
    assert loaded[0].stand == "2"
    assert loaded[1].stand == "A-1"

    # Update participant at index 0
    fresh_service.update_participant(
        participant_index=0,
        name="Альпина Новая",
        stand="1",
        link="https://new-alpina.ru",
        description="Новое описание",
    )
    assert fresh_service.get_participants()[0].name == "Альпина Новая"
    assert fresh_service.get_participants()[0].stand == "1"

    # Delete participant at index 1
    fresh_service.delete_participant(1)
    assert len(fresh_service.get_participants()) == 1
    assert fresh_service.get_participants()[0].name == "Альпина Новая"


def test_one_class_per_module_imports_participants():
    from bot.participants import Participant as PackageParticipant
    from bot.participants import ParticipantsService as PackageService
    from bot.participants.participant import Participant as DirectParticipant
    from bot.participants.service import ParticipantsService as DirectService

    assert PackageParticipant is DirectParticipant
    assert PackageService is DirectService


def test_admin_participants_service_url_validation(tmp_path):
    file_path = tmp_path / "participants.json"
    admin_service = AdminParticipantsService(file_path=str(file_path))

    # Valid URLs with protocol
    admin_service.add_participant(name="МИФ", stand="1", link="https://mif.ru")
    admin_service.add_participant(name="Альпина", stand="2", link="http://alpina.ru/catalog?id=10")
    assert len(admin_service.get_participants()) == 2

    # Mandatory name and stand checks
    with pytest.raises(ValueError, match="mandatory|empty"):
        admin_service.add_participant(name="", stand="3", link="https://example.com")

    with pytest.raises(ValueError, match="mandatory|empty"):
        admin_service.add_participant(name="Самокат", stand="", link="https://example.com")

    # Empty link is valid (only stand and name are mandatory)
    admin_service.add_participant(name="Самокат", stand="3", link="")
    assert len(admin_service.get_participants()) == 3
    assert admin_service.get_participants()[-1].link == ""

    # Valid URLs without protocol
    admin_service.add_participant(name="Бумкнига", stand="4", link="boomkniga.ru")
    admin_service.add_participant(name="Поляндрия", stand="5", link="polyandria.ru/catalog/books")
    assert len(admin_service.get_participants()) == 5

    # Invalid URLs on add
    with pytest.raises(ValueError, match="valid URL"):
        admin_service.add_participant(name="Тест", stand="6", link="invalid-url")

    with pytest.raises(ValueError, match="valid URL"):
        admin_service.add_participant(name="Тест 2", stand="7", link="ftp://example.com")

    with pytest.raises(ValueError, match="valid URL"):
        admin_service.add_participant(name="Тест 3", stand="8", link="https://")

    # Valid update with URL without protocol
    admin_service.update_participant(
        participant_index=0,
        name="МИФ",
        stand="1",
        link="mif.ru",
    )
    assert admin_service.get_participants()[0].link == "mif.ru"

    # Valid update with empty link
    admin_service.update_participant(
        participant_index=0,
        name="МИФ",
        stand="1",
        link="",
    )
    assert admin_service.get_participants()[0].link == ""

    # Invalid URL on update
    with pytest.raises(ValueError, match="valid URL"):
        admin_service.update_participant(
            participant_index=0,
            name="МИФ",
            stand="1",
            link="not_a_valid_url",
        )


def test_participants_template_format_and_no_placeholders():
    from admin.views.template_renderer import AdminTemplateRenderer

    tpl = AdminTemplateRenderer.load_template("participants.html")
    assert 'placeholder="' not in tpl
    assert '<input type="text" name="stand" class="form-control" required>' in tpl
    assert '<input type="text" name="name" class="form-control" required>' in tpl
    assert '<input type="text" id="addPartLink" name="link" class="form-control" autocomplete="off">' in tpl
    assert '<input type="text" id="editPartLink" name="link" class="form-control" autocomplete="off">' in tpl
    assert 'addPartLinkFeedback' in tpl
    assert 'editPartLinkFeedback' in tpl
    assert 'validateUrlInput' in tpl
