"""Tests for Admin Console locations panel and location rename propagation across events."""

import json
import os
import shutil
import tempfile
import pytest

from admin.auth.authenticator import AdminAuthenticator
from admin.auth.session_manager import AdminSessionManager
from admin.config import AdminConfig
from admin.server.request import AdminRequest
from admin.server.router import AdminRouter
from admin.services.timetable_service import AdminTimetableService
from admin.views.template_renderer import AdminTemplateRenderer


@pytest.fixture
def locations_test_env():
    """Create a temporary environment with multiple timetable dates and events."""
    temp_dir = tempfile.mkdtemp()
    timetables_dir = os.path.join(temp_dir, "timetables")
    os.makedirs(timetables_dir, exist_ok=True)

    day1 = {
        "date": "10092026",
        "events": [
            {
                "time": "10:00",
                "title": "Утренний Цигун",
                "location": "Сцена",
                "description": "Зарядка на свежем воздухе",
                "participants": ["Евгений Деменок"],
                "organizer": "Prague Book Tower",
                "is_children_activity": False,
            },
            {
                "time": "11:30",
                "title": "Мастер-класс для детей",
                "location": "Мастер-классы",
                "description": "Рисование персонажей",
                "participants": ["Эльга Попова"],
                "organizer": "Sandermoen Publishing",
                "is_children_activity": True,
            },
            {
                "time": "13:00",
                "title": "Читка книги",
                "location": "Сцена",
                "description": "Театральная читка",
                "participants": ["Агния Власова"],
                "organizer": "SamTamBooks",
                "is_children_activity": True,
            },
        ],
    }

    day2 = {
        "date": "11092026",
        "events": [
            {
                "time": "14:00",
                "title": "Круглый стол издателей",
                "location": "Сцена",
                "description": "Дискуссия о книгах",
                "participants": ["Иван Толстой"],
                "organizer": "Русская традиция",
                "is_children_activity": False,
            },
            {
                "time": "15:00",
                "title": "Воркшоп по письму",
                "location": "Мастер-классы",
                "description": "Пишем манифест",
                "participants": ["Инесса Сахно"],
                "organizer": "Prague Book Tower",
                "is_children_activity": False,
            },
            {
                "time": "16:00",
                "title": "Выставка иллюстраций",
                "location": "Галерея",
                "description": "Просмотр работ",
                "participants": [],
                "organizer": "Prague Book Tower",
                "is_children_activity": False,
            },
        ],
    }

    with open(os.path.join(timetables_dir, "10092026.json"), "w", encoding="utf-8") as f:
        json.dump(day1, f, ensure_ascii=False, indent=2)

    with open(os.path.join(timetables_dir, "11092026.json"), "w", encoding="utf-8") as f:
        json.dump(day2, f, ensure_ascii=False, indent=2)

    auth_db = os.path.join(temp_dir, "test_users.db")
    config = AdminConfig(
        host="127.0.0.1",
        port=0,
        auth_db_path=auth_db,
        assets_path=temp_dir,
        timetables_path=timetables_dir,
    )
    auth = AdminAuthenticator(config=config, db_path=auth_db)
    auth.create_admin_user("admin", "adminpass", is_confirmed=True)

    session_manager = AdminSessionManager(timeout_seconds=3600)
    token = session_manager.create_session()

    service = AdminTimetableService(directory_path=timetables_dir)
    router = AdminRouter(
        config=config,
        authenticator=auth,
        session_manager=session_manager,
        timetable_service=service,
    )

    yield {
        "temp_dir": temp_dir,
        "timetables_dir": timetables_dir,
        "service": service,
        "router": router,
        "token": token,
        "cookie": f"{config.session_cookie_name}={token}",
    }

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_get_locations_summary(locations_test_env):
    service = locations_test_env["service"]
    summary = service.get_locations_summary()

    # We expect 3 locations: Галерея, Мастер-классы, Сцена
    names = [s["name"] for s in summary]
    assert names == ["Галерея", "Мастер-классы", "Сцена"]

    scena = next(s for s in summary if s["name"] == "Сцена")
    assert scena["events_count"] == 3
    assert set(scena["days"]) == {"10092026", "11092026"}

    master = next(s for s in summary if s["name"] == "Мастер-классы")
    assert master["events_count"] == 2
    assert set(master["days"]) == {"10092026", "11092026"}

    gallery = next(s for s in summary if s["name"] == "Галерея")
    assert gallery["events_count"] == 1
    assert gallery["days"] == ["11092026"]


def test_rename_location_validation(locations_test_env):
    service = locations_test_env["service"]
    with pytest.raises(ValueError, match="Field 'old_name' is mandatory"):
        service.rename_location("", "Новая сцена")

    with pytest.raises(ValueError, match="Field 'new_name' is mandatory"):
        service.rename_location("Сцена", "  ")

    # Same name returns 0 and does not stage changes
    count = service.rename_location("Сцена", "Сцена")
    assert count == 0
    assert not service.has_pending_changes()


def test_rename_location_propagates_to_all_events(locations_test_env):
    service = locations_test_env["service"]
    timetables_dir = locations_test_env["timetables_dir"]

    # Rename "Сцена" to "Главная сцена"
    updated_count = service.rename_location("Сцена", "Главная сцена")
    assert updated_count == 3
    assert service.has_pending_changes()

    # Check in-memory staged data for day 1
    d1 = service.get_day_dict("10092026")
    assert d1["events"][0]["location"] == "Главная сцена"
    assert d1["events"][1]["location"] == "Мастер-классы"  # Untouched
    assert d1["events"][2]["location"] == "Главная сцена"

    # Check in-memory staged data for day 2
    d2 = service.get_day_dict("11092026")
    assert d2["events"][0]["location"] == "Главная сцена"
    assert d2["events"][1]["location"] == "Мастер-классы"
    assert d2["events"][2]["location"] == "Галерея"

    # Disk files should not be modified before commit
    with open(os.path.join(timetables_dir, "10092026.json"), "r", encoding="utf-8") as f:
        disk_d1 = json.load(f)
    assert disk_d1["events"][0]["location"] == "Сцена"

    # Save to disk
    service.save_to_disk()
    assert not service.has_pending_changes()

    with open(os.path.join(timetables_dir, "10092026.json"), "r", encoding="utf-8") as f:
        disk_d1_after = json.load(f)
    assert disk_d1_after["events"][0]["location"] == "Главная сцена"
    assert disk_d1_after["events"][2]["location"] == "Главная сцена"

    with open(os.path.join(timetables_dir, "11092026.json"), "r", encoding="utf-8") as f:
        disk_d2_after = json.load(f)
    assert disk_d2_after["events"][0]["location"] == "Главная сцена"


def test_rename_location_discard_changes(locations_test_env):
    service = locations_test_env["service"]
    service.rename_location("Мастер-классы", "Творческая мастерская")
    assert service.has_pending_changes()

    service.discard_changes()
    assert not service.has_pending_changes()

    # Reverted to disk
    d1 = service.get_day_dict("10092026")
    assert d1["events"][1]["location"] == "Мастер-классы"


def test_render_locations_template():
    summary = [
        {
            "name": "Сцена",
            "events_count": 5,
            "days": ["10092026", "11092026"],
        }
    ]
    html = AdminTemplateRenderer.render_locations(
        summary,
        message="Локация успешно обновлена",
        has_unsaved_changes=True,
    )
    assert "Управление локациями" in html
    assert "Сцена" in html
    assert "5 событий" in html
    assert "10.09.2026, 11.09.2026" in html
    assert "Локация успешно обновлена" in html
    assert "Есть несохраненные изменения" in html
    assert 'class="active">📍 Локации</a>' in html


def test_render_locations_empty_template():
    html = AdminTemplateRenderer.render_locations([], has_unsaved_changes=False)
    assert "Управление локациями" in html
    assert "Локации пока не добавлены в расписания" in html
    assert "(0 локаций)" in html


def test_router_get_locations(locations_test_env):
    router = locations_test_env["router"]
    cookie = locations_test_env["cookie"]

    req = AdminRequest(
        method="GET",
        path="/locations",
        headers={"Cookie": cookie},
    )
    res = router.route(req)
    assert res.status_code == 200
    assert "Управление локациями" in res.body.decode("utf-8")
    assert "Сцена" in res.body.decode("utf-8")
    assert "Мастер-классы" in res.body.decode("utf-8")
    assert "Галерея" in res.body.decode("utf-8")


def test_router_post_locations_rename(locations_test_env):
    router = locations_test_env["router"]
    cookie = locations_test_env["cookie"]
    service = locations_test_env["service"]

    req = AdminRequest(
        method="POST",
        path="/locations/rename",
        headers={"Cookie": cookie, "Content-Type": "application/x-www-form-urlencoded"},
        body=b"old_name=%D0%A1%D1%86%D0%B5%D0%BD%D0%B0&new_name=%D0%91%D0%BE%D0%BB%D1%8C%D1%88%D0%B0%D1%8F+%D0%A1%D1%86%D0%B5%D0%BD%D0%B0",
    )
    res = router.route(req)
    assert res.status_code == 302
    assert res.headers["Location"].startswith("/locations?msg=")

    # Verify events were renamed in service
    d1 = service.get_day_dict("10092026")
    assert d1["events"][0]["location"] == "Большая Сцена"
    assert d1["events"][2]["location"] == "Большая Сцена"


def test_router_post_locations_rename_validation_error(locations_test_env):
    router = locations_test_env["router"]
    cookie = locations_test_env["cookie"]

    req = AdminRequest(
        method="POST",
        path="/locations/rename",
        headers={"Cookie": cookie, "Content-Type": "application/x-www-form-urlencoded"},
        body=b"old_name=%D0%A1%D1%86%D0%B5%D0%BD%D0%B0&new_name=+++",
    )
    res = router.route(req)
    assert res.status_code == 302
    assert res.headers["Location"].startswith("/locations?error=")


def test_router_api_locations_rename(locations_test_env):
    router = locations_test_env["router"]
    cookie = locations_test_env["cookie"]
    service = locations_test_env["service"]

    req = AdminRequest(
        method="POST",
        path="/api/locations/rename",
        headers={"Cookie": cookie, "Content-Type": "application/json"},
        body=json.dumps({"old_name": "Галерея", "new_name": "Выставочный Зал"}).encode("utf-8"),
    )
    res = router.route(req)
    assert res.status_code == 200
    data = json.loads(res.body.decode("utf-8"))
    assert data["status"] == "ok"
    assert data["updated_events_count"] == 1

    d2 = service.get_day_dict("11092026")
    assert d2["events"][2]["location"] == "Выставочный Зал"


def test_router_save_and_discard_changes_with_return_to_locations(locations_test_env):
    router = locations_test_env["router"]
    cookie = locations_test_env["cookie"]
    timetables_dir = locations_test_env["timetables_dir"]

    # 1. Rename location
    req_rename = AdminRequest(
        method="POST",
        path="/locations/rename",
        headers={"Cookie": cookie, "Content-Type": "application/x-www-form-urlencoded"},
        body=b"old_name=%D0%A1%D1%86%D0%B5%D0%BD%D0%B0&new_name=%D0%9E%D1%81%D0%BD%D0%BE%D0%B2%D0%BD%D0%B0%D1%8F+%D0%A1%D1%86%D0%B5%D0%BD%D0%B0",
    )
    router.route(req_rename)
    assert router.has_unsaved_changes()

    # 2. Save changes with return_to=/locations
    req_save = AdminRequest(
        method="POST",
        path="/save-changes",
        headers={"Cookie": cookie, "Content-Type": "application/x-www-form-urlencoded"},
        body=b"return_to=%2Flocations",
    )
    res_save = router.route(req_save)
    assert res_save.status_code == 302
    assert res_save.headers["Location"].startswith("/locations?msg=")
    assert not router.has_unsaved_changes()

    # Verify written to disk
    with open(os.path.join(timetables_dir, "10092026.json"), "r", encoding="utf-8") as f:
        disk_data = json.load(f)
    assert disk_data["events"][0]["location"] == "Основная Сцена"

    # 3. Rename again and discard
    req_rename2 = AdminRequest(
        method="POST",
        path="/locations/rename",
        headers={"Cookie": cookie, "Content-Type": "application/x-www-form-urlencoded"},
        body=b"old_name=%D0%9E%D1%81%D0%BD%D0%BE%D0%B2%D0%BD%D0%B0%D1%8F+%D0%A1%D1%86%D0%B5%D0%BD%D0%B0&new_name=%D0%94%D1%80%D1%83%D0%B3%D0%B0%D1%8F+%D0%A1%D1%86%D0%B5%D0%BD%D0%B0",
    )
    router.route(req_rename2)
    assert router.has_unsaved_changes()

    req_discard = AdminRequest(
        method="POST",
        path="/discard-changes",
        headers={"Cookie": cookie, "Content-Type": "application/x-www-form-urlencoded"},
        body=b"return_to=%2Flocations",
    )
    res_discard = router.route(req_discard)
    assert res_discard.status_code == 302
    assert res_discard.headers["Location"].startswith("/locations?msg=")
    assert not router.has_unsaved_changes()


def test_rename_location_merging_into_existing(locations_test_env):
    service = locations_test_env["service"]

    # Before rename: Галерея (1 event), Мастер-классы (2 events)
    summary_before = service.get_locations_summary()
    assert len(summary_before) == 3

    # Merge Галерея into Мастер-классы
    count = service.rename_location("Галерея", "Мастер-классы")
    assert count == 1

    summary_after = service.get_locations_summary()
    assert len(summary_after) == 2
    master = next(s for s in summary_after if s["name"] == "Мастер-классы")
    assert master["events_count"] == 3  # 2 + 1
