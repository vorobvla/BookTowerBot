"""Unit tests for Master Classes feature across bot, services, sections, and admin."""

import json
from unittest.mock import AsyncMock, MagicMock
import pytest

from admin.server.request import AdminRequest
from admin.server.router import AdminRouter
from admin.services.timetable_service import AdminTimetableService
from admin.views.template_renderer import AdminTemplateRenderer
from bot.content import (
    BTN_MASTER_CLASSES,
    BTN_MC_ALL,
    BTN_MC_FOR_CHILDREN,
    CB_MASTER_CLASSES,
    CB_MC_FILTER_ALL,
    CB_MC_FILTER_CHILDREN,
    CB_MC_ITEM_PREFIX,
    MASTER_CLASSES_CHILDREN_EMPTY_MESSAGE,
    MASTER_CLASSES_CHILDREN_MESSAGE,
    MASTER_CLASSES_EMPTY_MESSAGE,
    MASTER_CLASSES_MESSAGE,
)
from bot.sections.master_classes import MasterClasses
from bot.timetable.day import DayTimetable
from bot.timetable.event import Event
from bot.timetable.service import TimetableService


def test_event_master_class_flag():
    # Default is False
    ev_default = Event(time="10:00", title="Встреча")
    assert ev_default.is_master_class is False
    assert ev_default.to_dict()["is_master_class"] is False

    # From dict boolean True
    ev_true = Event.from_dict({
        "time": "11:00",
        "title": "Мастер-класс по акварели",
        "is_master_class": True,
        "is_children_activity": True,
    })
    assert ev_true.is_master_class is True
    assert ev_true.is_children_activity is True
    assert ev_true.to_dict()["is_master_class"] is True

    # From dict string truthy values
    ev_str = Event.from_dict({
        "time": "12:00",
        "title": "Каллиграфия",
        "is_master_class": "1",
    })
    assert ev_str.is_master_class is True

    # From dict alternate key is_masterclass
    ev_alt = Event.from_dict({
        "time": "13:00",
        "title": "Робототехника",
        "is_masterclass": True,
    })
    assert ev_alt.is_master_class is True


def test_day_timetable_get_master_classes():
    ev_normal = Event(time="10:00", title="Презентация книги", is_master_class=False)
    ev_mc_adult = Event(time="11:00", title="Мастер-класс для взрослых", is_master_class=True, is_children_activity=False)
    ev_mc_kids = Event(time="12:00", title="Детский мастер-класс", is_master_class=True, is_children_activity=True)
    ev_kids_other = Event(time="13:00", title="Сказкотерапия", is_master_class=False, is_children_activity=True)

    day = DayTimetable(date="10092026", events=[ev_normal, ev_mc_adult, ev_mc_kids, ev_kids_other])

    all_mc = day.get_master_classes(children_only=False)
    assert len(all_mc) == 2
    assert ev_mc_adult in all_mc
    assert ev_mc_kids in all_mc
    assert ev_normal not in all_mc
    assert ev_kids_other not in all_mc

    kids_mc = day.get_master_classes(children_only=True)
    assert len(kids_mc) == 1
    assert kids_mc[0] == ev_mc_kids


def test_timetable_service_master_classes(tmp_path):
    day1_data = {
        "date": "10092026",
        "events": [
            {
                "time": "11:00",
                "title": "Мастер-класс 1",
                "location": "Зал 1",
                "is_master_class": True,
                "is_children_activity": False,
            },
            {
                "time": "15:00",
                "title": "Мастер-класс для детей 1",
                "location": "Детский шатер",
                "is_master_class": True,
                "is_children_activity": True,
            },
        ],
    }
    day2_data = {
        "date": "11092026",
        "events": [
            {
                "time": "12:00",
                "title": "Лекция",
                "location": "Зал 2",
                "is_master_class": False,
            },
            {
                "time": "16:00",
                "title": "Мастер-класс для детей 2",
                "location": "Детский шатер",
                "description": "Учимся рисовать иллюстрации",
                "participants": ["Художник Анна"],
                "organizer": "Издательство",
                "is_master_class": True,
                "is_children_activity": True,
            },
        ],
    }

    with open(tmp_path / "10092026.json", "w", encoding="utf-8") as f:
        json.dump(day1_data, f)
    with open(tmp_path / "11092026.json", "w", encoding="utf-8") as f:
        json.dump(day2_data, f)

    service = TimetableService(timetables_dir=str(tmp_path))

    # All master classes across dates
    all_mc = service.get_master_classes(children_only=False)
    assert len(all_mc) == 3
    assert all_mc[0][0] == "10092026"
    assert all_mc[0][2].title == "Мастер-класс 1"
    assert all_mc[1][0] == "10092026"
    assert all_mc[1][2].title == "Мастер-класс для детей 1"
    assert all_mc[2][0] == "11092026"
    assert all_mc[2][2].title == "Мастер-класс для детей 2"

    # Children only master classes
    kids_mc = service.get_master_classes(children_only=True)
    assert len(kids_mc) == 2
    assert kids_mc[0][2].title == "Мастер-класс для детей 1"
    assert kids_mc[1][2].title == "Мастер-класс для детей 2"

    # get_master_class by date and index
    item = service.get_master_class("11092026", 1)
    assert item is not None
    assert item.title == "Мастер-класс для детей 2"

    non_item = service.get_master_class("11092026", 99)
    assert non_item is None

    # format_master_class_details
    details_md = service.format_master_class_details("11092026", item)
    assert "🎨 *Мастер-класс: Мастер-класс для детей 2*" in details_md
    assert "📅 *Дата:* 11.09.2026" in details_md
    assert "⌚ *Время:* 16:00" in details_md
    assert "📍 *Площадка:* Детский шатер" in details_md
    assert "🎈 *Программа:* Детская программа" in details_md
    assert "👥 *Ведущие / Участники:* Художник Анна" in details_md
    assert "📖 *Организатор:* Издательство" in details_md
    assert "Учимся рисовать иллюстрации" in details_md


@pytest.mark.asyncio
async def test_master_classes_section_workflow():
    mock_service = MagicMock(spec=TimetableService)
    ev_adult = Event(time="10:00", title="Мастер-класс живописи", location="Зал 1", is_master_class=True, is_children_activity=False)
    ev_kids = Event(time="14:00", title="Детский мастер-класс оригами", location="Зал 2", is_master_class=True, is_children_activity=True)

    def mock_get_mc(children_only=False):
        if children_only:
            return [("10092026", 1, ev_kids)]
        return [("10092026", 0, ev_adult), ("10092026", 1, ev_kids)]

    def mock_get_single(date_str, idx):
        if date_str == "10092026" and idx == 0:
            return ev_adult
        if date_str == "10092026" and idx == 1:
            return ev_kids
        return None

    mock_service.get_master_classes.side_effect = mock_get_mc
    mock_service.get_master_class.side_effect = mock_get_single
    mock_service.format_date_label.return_value = "10.09.2026"
    mock_service.format_master_class_details.return_value = "Детали мастер-класса"

    section = MasterClasses(service=mock_service)

    # Command matching
    assert section.matches_command("masterclasses")
    assert section.matches_command("/masterclasses")
    assert section.matches_command("masterclass")
    assert section.matches_command("mc")
    assert section.matches_command("master_classes")
    assert not section.matches_command("timetable")

    # Text / Button matching
    assert section.matches_text(BTN_MASTER_CLASSES)
    assert section.matches_text("Мастер-классы")
    assert section.matches_text("мастер классы")
    assert section.matches_text("мастер-класс")

    # Callback matching
    assert section.matches_callback(CB_MASTER_CLASSES)
    assert section.matches_callback(CB_MC_FILTER_ALL)
    assert section.matches_callback(CB_MC_FILTER_CHILDREN)
    assert section.matches_callback(f"{CB_MC_ITEM_PREFIX}10092026:0:0")
    assert not section.matches_callback("action_map")

    # send_response
    mock_msg = AsyncMock()
    await section.send_response(mock_msg)
    mock_msg.reply_text.assert_awaited_once()
    assert mock_msg.reply_text.call_args.kwargs["text"] == MASTER_CLASSES_MESSAGE

    # Callback: Filter all (default)
    query_all = AsyncMock()
    query_all.data = CB_MC_FILTER_ALL
    await section.handle_callback_query(query_all)
    query_all.edit_message_text.assert_awaited_once()
    assert query_all.edit_message_text.call_args.kwargs["text"] == MASTER_CLASSES_MESSAGE
    kb_all = query_all.edit_message_text.call_args.kwargs["reply_markup"]
    assert kb_all.inline_keyboard[0][0].text == BTN_MC_FOR_CHILDREN

    # Callback: Filter children
    query_kids = AsyncMock()
    query_kids.data = CB_MC_FILTER_CHILDREN
    await section.handle_callback_query(query_kids)
    query_kids.edit_message_text.assert_awaited_once()
    assert query_kids.edit_message_text.call_args.kwargs["text"] == MASTER_CLASSES_CHILDREN_MESSAGE
    kb_kids = query_kids.edit_message_text.call_args.kwargs["reply_markup"]
    assert kb_kids.inline_keyboard[0][0].text == BTN_MC_ALL

    # Callback: Show details of adult master-class
    query_item = AsyncMock()
    query_item.data = f"{CB_MC_ITEM_PREFIX}10092026:0:0"
    await section.handle_callback_query(query_item)
    query_item.edit_message_text.assert_awaited_once()
    assert query_item.edit_message_text.call_args.kwargs["text"] == "Детали мастер-класса"
    kb_item = query_item.edit_message_text.call_args.kwargs["reply_markup"]
    assert kb_item.inline_keyboard[0][0].callback_data == CB_MC_FILTER_ALL

    # Callback: Show details of kids master-class
    query_kids_item = AsyncMock()
    query_kids_item.data = f"{CB_MC_ITEM_PREFIX}10092026:1:1"
    await section.handle_callback_query(query_kids_item)
    query_kids_item.edit_message_text.assert_awaited_once()
    kb_kids_item = query_kids_item.edit_message_text.call_args.kwargs["reply_markup"]
    assert kb_kids_item.inline_keyboard[0][0].callback_data == CB_MC_FILTER_CHILDREN


@pytest.mark.asyncio
async def test_master_classes_empty_handling():
    mock_service = MagicMock(spec=TimetableService)
    mock_service.get_master_classes.return_value = []
    section = MasterClasses(service=mock_service)

    assert section.get_text_content(children_only=False) == MASTER_CLASSES_EMPTY_MESSAGE
    assert section.get_text_content(children_only=True) == MASTER_CLASSES_CHILDREN_EMPTY_MESSAGE


def test_admin_timetable_service_master_class(tmp_path):
    service = AdminTimetableService(directory_path=str(tmp_path))
    date_key = service.create_day("10092026")

    # Add event with is_master_class=True
    service.add_event(
        date=date_key,
        time="11:00",
        title="Мастер-класс анимации",
        location="Сцена 1",
        is_children_activity=True,
        is_master_class=True,
    )

    day_dict = service.get_day_dict(date_key)
    assert len(day_dict["events"]) == 1
    assert day_dict["events"][0]["is_master_class"] is True
    assert day_dict["events"][0]["is_children_activity"] is True

    # Update event with is_master_class=False
    service.update_event(
        date=date_key,
        event_index=0,
        time="11:30",
        title="Мастер-класс анимации (обновлен)",
        location="Сцена 1",
        is_children_activity=False,
        is_master_class=False,
    )
    day_dict = service.get_day_dict(date_key)
    assert day_dict["events"][0]["is_master_class"] is False
    assert day_dict["events"][0]["time"] == "11:30"

    # Toggle master class flag
    new_val = service.toggle_event_master_class(date_key, 0)
    assert new_val is True
    assert service.get_day_dict(date_key)["events"][0]["is_master_class"] is True

    # Set master class flag directly
    service.set_event_master_class(date_key, 0, False)
    assert service.get_day_dict(date_key)["events"][0]["is_master_class"] is False


def test_admin_renderer_master_class_rendering():
    event = Event(
        time="10:00",
        title="Гончарный мастер-класс",
        location="Студия",
        is_children_activity=True,
        is_master_class=True,
    )
    day = DayTimetable(date="10092026", events=[event])

    html_out = AdminTemplateRenderer.render_day_timetable(
        date_key="10092026",
        timetable=day,
        all_locations=["Студия"],
    )

    assert "Мастер-класс" in html_out
    assert 'name="is_master_class"' in html_out
    assert 'checked' in html_out
    assert 'data-masterclass="1"' in html_out


def test_admin_router_master_class_routes(tmp_path):
    tt_service = AdminTimetableService(directory_path=str(tmp_path))
    date_key = tt_service.create_day("10092026")
    router = AdminRouter(timetable_service=tt_service)
    headers = {
        "Cookie": f"{router.config.session_cookie_name}=valid_mock",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    router.session_manager.is_valid_session = MagicMock(return_value=True)

    # Add event POST
    body_add = "time=12%3A00&title=Шелкография&location_select=__NEW__&custom_location=Цех&is_children_activity=1&is_master_class=1".encode("utf-8")
    req_add = AdminRequest(
        method="POST",
        path=f"/timetables/{date_key}/events/add",
        headers=headers,
        body=body_add,
    )
    res_add = router.route(req_add)
    assert res_add.status_code == 302
    assert tt_service.get_day_dict(date_key)["events"][0]["is_master_class"] is True
    assert tt_service.get_day_dict(date_key)["events"][0]["is_children_activity"] is True

    # Update event POST
    body_upd = "event_index=0&time=12%3A00&title=Шелкография+обновленная&location_select=Цех&is_children_activity=0&is_master_class=0".encode("utf-8")
    req_upd = AdminRequest(
        method="POST",
        path=f"/timetables/{date_key}/events/update",
        headers=headers,
        body=body_upd,
    )
    res_upd = router.route(req_upd)
    assert res_upd.status_code == 302
    assert tt_service.get_day_dict(date_key)["events"][0]["is_master_class"] is False

    # Toggle master class POST
    body_toggle = "event_index=0".encode("utf-8")
    req_toggle = AdminRequest(
        method="POST",
        path=f"/timetables/{date_key}/events/toggle_master_class",
        headers=headers,
        body=body_toggle,
    )
    res_toggle = router.route(req_toggle)
    assert res_toggle.status_code == 302
    assert tt_service.get_day_dict(date_key)["events"][0]["is_master_class"] is True


def test_admin_timetable_service_get_all_master_classes(tmp_path):
    service = AdminTimetableService(directory_path=str(tmp_path))
    day1 = service.create_day("10092026")
    day2 = service.create_day("11092026")

    # Day 1: 1 regular, 1 master class
    service.add_event(
        date=day1,
        time="10:00",
        title="Обычная лекция",
        location="Главный зал",
        is_master_class=False,
    )
    service.add_event(
        date=day1,
        time="12:00",
        title="Мастер-класс по оригами",
        location="Творческая зона",
        is_master_class=True,
        is_children_activity=True,
    )

    # Day 2: 1 master class
    service.add_event(
        date=day2,
        time="14:00",
        title="Мастер-класс по иллюстрации",
        location="Мастерская",
        is_master_class=True,
        is_children_activity=False,
    )

    all_mc = service.get_all_master_classes()
    assert len(all_mc) == 2
    assert all_mc[0]["title"] == "Мастер-класс по оригами"
    assert all_mc[0]["date_key"] == "10092026"
    assert all_mc[0]["event_index"] == 1
    assert all_mc[0]["is_children_activity"] is True
    assert all_mc[1]["title"] == "Мастер-класс по иллюстрации"
    assert all_mc[1]["date_key"] == "11092026"
    assert all_mc[1]["event_index"] == 0
    assert all_mc[1]["is_children_activity"] is False


def test_admin_renderer_timetables_list_master_classes():
    # Empty master classes
    html_empty = AdminTemplateRenderer.render_timetables_list(
        dates=["10092026"],
        master_classes=[],
    )
    assert "Все мастер-классы" in html_empty
    assert "Нет запланированных мастер-классов" in html_empty

    # With master classes
    mc_data = [
        {
            "date_key": "10092026",
            "event_index": 0,
            "time": "11:00",
            "title": "Мастер-класс по акварели",
            "location": "Павильон 3",
            "organizer": "Арт-клуб",
            "participants": ["Художник Иван"],
            "description": "Рисуем обложку книги",
            "is_children_activity": True,
            "is_master_class": True,
        }
    ]
    html_with_mc = AdminTemplateRenderer.render_timetables_list(
        dates=["10092026"],
        master_classes=mc_data,
        all_locations=["Павильон 3", "Мастерская"],
    )
    assert "Все мастер-классы" in html_with_mc
    assert "10.09.2026" in html_with_mc
    assert "11:00" in html_with_mc
    assert "Мастер-класс по акварели" in html_with_mc
    assert "Павильон 3" in html_with_mc
    assert "Арт-клуб" in html_with_mc
    assert "Художник Иван" in html_with_mc
    assert "Рисуем обложку книги" in html_with_mc
    assert "/timetables/10092026" in html_with_mc
    assert 'name="is_master_class"' in html_with_mc
    assert 'name="is_children_activity"' in html_with_mc
    assert "Перейти к дню" not in html_with_mc
    assert "Редактировать" in html_with_mc
    assert "openEditEventModal(this)" in html_with_mc
    assert 'data-date="10092026"' in html_with_mc
    assert "editEventModalBackdrop" in html_with_mc
    assert "Павильон 3" in html_with_mc


def test_admin_router_timetables_master_classes_panel_and_redirects(tmp_path):
    tt_service = AdminTimetableService(directory_path=str(tmp_path))
    date_key = tt_service.create_day("10092026")
    router = AdminRouter(timetable_service=tt_service)
    headers = {
        "Cookie": f"{router.config.session_cookie_name}=valid_mock",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    router.session_manager.is_valid_session = MagicMock(return_value=True)

    # Add master class event
    tt_service.add_event(
        date=date_key,
        time="15:00",
        title="Мастер-класс по переплету",
        location="Мастерская 2",
        is_master_class=True,
    )

    # GET /timetables should show master-class panel
    req_get = AdminRequest(method="GET", path="/timetables", headers=headers)
    res_get = router.route(req_get)
    assert res_get.status_code == 200
    html_body = res_get.body.decode("utf-8")
    assert "Все мастер-классы" in html_body
    assert "Мастер-класс по переплету" in html_body

    # Toggle children activity with return_to=/timetables
    body_toggle_child = "event_index=0&return_to=%2Ftimetables".encode("utf-8")
    req_toggle_child = AdminRequest(
        method="POST",
        path=f"/timetables/{date_key}/events/toggle_children",
        headers=headers,
        body=body_toggle_child,
    )
    res_toggle_child = router.route(req_toggle_child)
    assert res_toggle_child.status_code == 302
    assert res_toggle_child.headers["Location"] == "/timetables"
    assert tt_service.get_day_dict(date_key)["events"][0]["is_children_activity"] is True

    # Toggle master class with return_to=/timetables
    body_toggle_mc = "event_index=0&return_to=%2Ftimetables".encode("utf-8")
    req_toggle_mc = AdminRequest(
        method="POST",
        path=f"/timetables/{date_key}/events/toggle_master_class",
        headers=headers,
        body=body_toggle_mc,
    )
    res_toggle_mc = router.route(req_toggle_mc)
    assert res_toggle_mc.status_code == 302
    assert res_toggle_mc.headers["Location"] == "/timetables"
    assert tt_service.get_day_dict(date_key)["events"][0]["is_master_class"] is False

    # Edit event with return_to=/timetables
    body_edit = (
        "event_index=0&return_to=%2Ftimetables&time=16%3A00&title=%D0%9E%D0%B1%D0%BD%D0%BE%D0%B2%D0%BB%D0%B5%D0%BD%D0%BD%D1%8B%D0%B9+%D0%BC%D0%B0%D1%81%D1%82%D0%B5%D1%80-%D0%BA%D0%BB%D0%B0%D1%81%D1%81&location=%D0%93%D0%BB%D0%B0%D0%B2%D0%BD%D1%8B%D0%B9+%D0%B7%D0%B0%D0%BB&is_master_class=1"
    ).encode("utf-8")
    req_edit = AdminRequest(
        method="POST",
        path=f"/timetables/{date_key}/events/update",
        headers=headers,
        body=body_edit,
    )
    res_edit = router.route(req_edit)
    assert res_edit.status_code == 302
    assert res_edit.headers["Location"].startswith("/timetables?msg=")
    updated_event = tt_service.get_day_dict(date_key)["events"][0]
    assert updated_event["time"] == "16:00"
    assert updated_event["title"] == "Обновленный мастер-класс"
    assert updated_event["location"] == "Главный зал"
    assert updated_event["is_master_class"] is True

    # Also verify day timetable page still retains events in general/children panels
    req_day = AdminRequest(method="GET", path=f"/timetables/{date_key}", headers=headers)
    res_day = router.route(req_day)
    assert res_day.status_code == 200
    html_day = res_day.body.decode("utf-8")
    assert "Обновленный мастер-класс" in html_day
