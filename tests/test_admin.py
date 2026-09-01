"""Comprehensive tests for the BookTower Admin Console."""

import json
import os
import shutil
import tempfile
import urllib.request
from typing import Dict
import pytest

from admin.app import AdminApp
from admin.auth.authenticator import AdminAuthenticator
from admin.auth.session_manager import AdminSessionManager
from admin.config import AdminConfig
from admin.server.request import AdminRequest
from admin.server.response import AdminResponse
from admin.server.router import AdminRouter
from admin.services.recs_service import AdminRecsService
from admin.services.timetable_service import AdminTimetableService
from admin.views.template_renderer import AdminTemplateRenderer, TEMPLATES_DIR
from bot.recommendations.book import Book
from bot.recommendations.category import RecommendationCategory
from bot.timetable.day import DayTimetable
from bot.timetable.event import Event


@pytest.fixture
def temp_admin_env():
    """Create a temporary directory with recs.json and timetables for testing."""
    temp_dir = tempfile.mkdtemp()
    recs_dir = os.path.join(temp_dir, "recs")
    os.makedirs(recs_dir, exist_ok=True)
    recs_file = os.path.join(recs_dir, "recs.json")

    initial_recs = {
        "recs": [
            {
                "rec": "Нонфикшн",
                "books": [
                    {
                        "title": "Книга Жопова",
                        "description": "Описание",
                        "authors": ["Вася Жопов"],
                        "soldBy": ["Стенд 123"],
                    }
                ],
            }
        ]
    }
    with open(recs_file, "w", encoding="utf-8") as f:
        json.dump(initial_recs, f)

    timetables_dir = os.path.join(temp_dir, "timetables")
    os.makedirs(timetables_dir, exist_ok=True)
    day_file = os.path.join(timetables_dir, "10092026.json")
    initial_day = {
        "date": "10092026",
        "events": [
            {
                "time": "10:00",
                "title": "Открытие фестиваля",
                "description": "Вводная речь",
                "participants": ["Ведущий"],
                "organizer": "Оргкомитет",
                "location": "Главная сцена",
            }
        ],
    }
    with open(day_file, "w", encoding="utf-8") as f:
        json.dump(initial_day, f)

    config = AdminConfig(
        host="127.0.0.1",
        port=0,
        username="testadmin",
        password="testpassword",
        assets_path=temp_dir,
        recs_path=recs_file,
        timetables_path=timetables_dir,
    )

    yield config, recs_file, timetables_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


# --- Authentication & Session Tests ---

def test_authenticator(temp_admin_env):
    config, _, _ = temp_admin_env
    auth = AdminAuthenticator(config)

    assert auth.authenticate("testadmin", "testpassword") is True
    assert auth.authenticate("testadmin", "wrong") is False
    assert auth.authenticate("wrong", "testpassword") is False
    assert auth.authenticate("", "") is False
    assert auth.authenticate(None, None) is False


def test_session_manager():
    sm = AdminSessionManager(timeout_seconds=3600)
    token = sm.create_session()
    assert isinstance(token, str) and len(token) > 0
    assert sm.is_valid_session(token) is True
    assert sm.is_valid_session("non_existent_token") is False

    sm.revoke_session(token)
    assert sm.is_valid_session(token) is False


def test_session_manager_expiration():
    sm = AdminSessionManager(timeout_seconds=-1)  # expired immediately
    token = sm.create_session()
    assert sm.is_valid_session(token) is False


# --- AdminRecsService Tests ---

def test_recs_service_crud_and_validation(temp_admin_env):
    _, recs_file, _ = temp_admin_env
    service = AdminRecsService(recs_file)

    # 1. Load initial
    categories = service.get_categories()
    assert len(categories) == 1
    assert categories[0].name == "Нонфикшн"
    assert categories[0].books[0].title == "Книга Жопова"

    # 2. Add Category
    service.add_category("Детская литература")
    assert len(service.get_categories()) == 2

    # Duplicate category error
    with pytest.raises(ValueError, match="already exists"):
        service.add_category("Детская литература")

    # Empty category error
    with pytest.raises(ValueError, match="cannot be empty"):
        service.add_category("   ")

    # 3. Add Book - Mandatory fields check
    # Missing title error
    with pytest.raises(ValueError, match="Field 'title' is mandatory"):
        service.add_book("Детская литература", title="", sold_by=["Магазин 1"])

    # Missing soldBy error
    with pytest.raises(ValueError, match="Field 'sold by' is mandatory"):
        service.add_book("Детская литература", title="Сказка", sold_by=[])

    with pytest.raises(ValueError, match="Field 'sold by' is mandatory"):
        service.add_book("Детская литература", title="Сказка", sold_by="   ")

    # Valid add book
    service.add_book(
        category_name="Детская литература",
        title="Сказки для детей",
        sold_by="Издательство 1, Стенд C2",
        authors="Автор А, Автор Б",
        description="Хорошая книга",
    )

    # Verify data consistency with bot's RecommendationCategory model
    raw_data = service.load_data()
    bot_cat = RecommendationCategory.from_dict(raw_data["recs"][1])
    assert bot_cat.name == "Детская литература"
    assert len(bot_cat.books) == 1
    book = bot_cat.books[0]
    assert book.title == "Сказки для детей"
    assert book.authors == ["Автор А", "Автор Б"]
    assert book.sold_by == ["Издательство 1", "Стенд C2"]
    assert book.description == "Хорошая книга"

    # 4. Update and Delete Book
    service.update_book(
        category_name="Детская литература",
        book_index=0,
        title="Обновленные сказки",
        sold_by=["Стенд C2"],
        description="Новое описание",
    )
    assert service.get_categories()[1].books[0].title == "Обновленные сказки"

    service.delete_book("Детская литература", 0)
    assert len(service.get_categories()[1].books) == 0

    # 5. Rename & Delete Category
    service.rename_category("Детская литература", "Сказки")
    assert service.get_categories()[1].name == "Сказки"

    service.delete_category("Сказки")
    assert len(service.get_categories()) == 1


# --- AdminTimetableService Tests ---

def test_timetable_service_crud_and_validation(temp_admin_env):
    _, _, timetables_dir = temp_admin_env
    service = AdminTimetableService(timetables_dir)

    # 1. List days & get locations
    assert service.list_days() == ["10092026"]
    assert service.get_all_locations() == ["Главная сцена"]

    # 2. Create new day
    service.create_day("11092026")
    assert "11092026" in service.list_days()

    with pytest.raises(ValueError, match="already exists"):
        service.create_day("11092026")

    # 3. Add Event - Mandatory fields check
    # Missing time error
    with pytest.raises(ValueError, match="Field 'time' is mandatory"):
        service.add_event("11092026", time="", title="Презентация", location="Сцена 1")

    # Missing title error
    with pytest.raises(ValueError, match="Field 'title' is mandatory"):
        service.add_event("11092026", time="12:00", title="  ", location="Сцена 1")

    # Missing location error
    with pytest.raises(ValueError, match="Field 'location' is mandatory"):
        service.add_event("11092026", time="12:00", title="Презентация", location="")

    # Valid add event
    service.add_event(
        date="11092026",
        time="12:00",
        title="Круглый стол",
        location="Конференц-зал 2",
        organizer="Издательство А",
        participants=["Спикер 1", "Спикер 2"],
        description="Обсуждение трендов",
    )

    # Save staged changes to disk and verify file creation & data consistency
    assert service.has_pending_changes() is True
    service.save_to_disk()
    assert service.has_pending_changes() is False

    day_model = DayTimetable.from_file(os.path.join(timetables_dir, "11092026.json"))
    assert day_model.date == "11092026"
    assert len(day_model.events) == 1
    event = day_model.events[0]
    assert event.time == "12:00"
    assert event.title == "Круглый стол"
    assert event.location == "Конференц-зал 2"
    assert event.organizer == "Издательство А"
    assert event.participants == ["Спикер 1", "Спикер 2"]

    # Verify locations dropdown collection contains all locations across files
    all_locs = service.get_all_locations()
    assert "Главная сцена" in all_locs
    assert "Конференц-зал 2" in all_locs

    # 4. Update and delete event
    service.update_event(
        date="11092026",
        event_index=0,
        time="13:00",
        title="Обновленный стол",
        location="Главная сцена",
    )
    updated_day = service.get_day_timetable("11092026")
    assert updated_day.events[0].time == "13:00"
    assert updated_day.events[0].title == "Обновленный стол"

    service.delete_event("11092026", 0)
    assert len(service.get_day_timetable("11092026").events) == 0

    # 5. Delete day
    service.delete_day("11092026")
    assert "11092026" not in service.list_days()


# --- AdminRouter & Web Flow Tests ---

def test_router_auth_guard_and_login_flow(temp_admin_env):
    config, _, _ = temp_admin_env
    router = AdminRouter(config=config)

    # 1. Unauthenticated access to /timetables redirects to /login
    req_unauth = AdminRequest(method="GET", path="/timetables", headers={})
    resp = router.route(req_unauth)
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"

    # API unauthenticated access returns 401
    req_api_unauth = AdminRequest(method="GET", path="/api/timetables", headers={})
    resp_api = router.route(req_api_unauth)
    assert resp_api.status_code == 401

    # 2. Login GET returns login HTML
    req_login_get = AdminRequest(method="GET", path="/login", headers={})
    resp_login_get = router.route(req_login_get)
    assert resp_login_get.status_code == 200
    assert b"BookTower Admin" in resp_login_get.body

    # 3. Login POST with invalid credentials fails
    req_login_fail = AdminRequest(
        method="POST",
        path="/login",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=b"username=testadmin&password=wrongpassword",
    )
    resp_login_fail = router.route(req_login_fail)
    assert resp_login_fail.status_code == 401
    assert "Неверное имя" in resp_login_fail.body.decode("utf-8")

    # 4. Login POST with valid credentials succeeds and returns cookie
    req_login_ok = AdminRequest(
        method="POST",
        path="/login",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=b"username=testadmin&password=testpassword",
    )
    resp_login_ok = router.route(req_login_ok)
    assert resp_login_ok.status_code == 302
    assert resp_login_ok.headers["Location"] == "/timetables"
    assert len(resp_login_ok.cookies) == 1
    session_cookie = resp_login_ok.cookies[0].split(";")[0]

    # 5. Authenticated access using session cookie
    auth_headers = {"Cookie": session_cookie}
    req_auth = AdminRequest(method="GET", path="/timetables", headers=auth_headers)
    resp_auth = router.route(req_auth)
    assert resp_auth.status_code == 200
    assert "Управление расписаниями" in resp_auth.body.decode("utf-8")

    # 6. Logout clears session
    req_logout = AdminRequest(method="GET", path="/logout", headers=auth_headers)
    resp_logout = router.route(req_logout)
    assert resp_logout.status_code == 302
    assert resp_logout.headers["Location"] == "/login"

    # Subsequent request with old cookie fails
    req_reauth = AdminRequest(method="GET", path="/timetables", headers=auth_headers)
    assert router.route(req_reauth).status_code == 302


def test_router_recs_and_timetables_web_operations(temp_admin_env):
    config, _, _ = temp_admin_env
    router = AdminRouter(config=config)

    # Authenticate and obtain session token
    token = router.session_manager.create_session()
    cookie = f"{config.session_cookie_name}={token}"
    headers = {
        "Cookie": cookie,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # Add book to recommendations
    body_book = "category_name=Нонфикшн&title=Новая+Книга&sold_by=Стенд+А1&authors=Автор&description=Описание".encode("utf-8")
    req_add_book = AdminRequest(method="POST", path="/recs/book/add", headers=headers, body=body_book)
    resp_add_book = router.route(req_add_book)
    assert resp_add_book.status_code == 302

    # View recs page
    req_recs = AdminRequest(method="GET", path="/recs", headers={"Cookie": cookie})
    resp_recs = router.route(req_recs)
    assert resp_recs.status_code == 200
    html_recs = resp_recs.body.decode("utf-8")
    assert "Новая Книга" in html_recs
    assert "Стенд А1" in html_recs

    # Add event with custom location to timetable
    body_event = "time=15:00&title=Мастер-класс&location_select=__NEW__&custom_location=Новый+Павильон+Z".encode("utf-8")
    req_add_event = AdminRequest(method="POST", path="/timetables/10092026/events/add", headers=headers, body=body_event)
    resp_add_event = router.route(req_add_event)
    assert resp_add_event.status_code == 302

    # View day timetable
    req_day = AdminRequest(method="GET", path="/timetables/10092026", headers={"Cookie": cookie})
    resp_day = router.route(req_day)
    assert resp_day.status_code == 200
    html_day = resp_day.body.decode("utf-8")
    assert "Мастер-класс" in html_day
    assert "Новый Павильон Z" in html_day
    assert "option value=" in html_day  # location dropdown rendered


# --- Full HTTP Server Integration Test ---

def test_admin_http_server_end_to_end(temp_admin_env):
    import socket
    # Pick a random free port
    with socket.socket() as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    config_base, _, _ = temp_admin_env
    server_config = AdminConfig(
        host="127.0.0.1",
        port=port,
        username="admin",
        password="secretpassword",
        assets_path=config_base.assets_path,
        recs_path=config_base.recs_path,
        timetables_path=config_base.timetables_path,
    )

    app = AdminApp(server_config)
    app.run(background=True)

    try:
        base_url = f"http://127.0.0.1:{port}"

        # 1. Login via HTTP POST
        login_data = "username=admin&password=secretpassword".encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        # urllib follows redirects; let's capture cookies
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        try:
            resp = opener.open(req)
            cookie_header = resp.headers.get("Set-Cookie")
        except urllib.error.HTTPError as e:
            assert e.code == 302
            cookie_header = e.headers.get("Set-Cookie")

        assert cookie_header is not None
        cookie = cookie_header.split(";")[0]

        # 2. Query API endpoints with cookie
        api_req = urllib.request.Request(
            f"{base_url}/api/timetables",
            headers={"Cookie": cookie},
        )
        with urllib.request.urlopen(api_req) as api_resp:
            assert api_resp.status == 200
            data = json.loads(api_resp.read().decode("utf-8"))
            assert "10092026" in data

        # 3. Query Recs HTML with cookie
        recs_req = urllib.request.Request(
            f"{base_url}/recs",
            headers={"Cookie": cookie},
        )
        with urllib.request.urlopen(recs_req) as recs_resp:
            assert recs_resp.status == 200
            assert b"BookTower Admin" in recs_resp.read()

    finally:
        app.stop()


# --- AdminTemplateRenderer Unit Tests ---

def test_template_files_exist_and_not_empty():
    """Verify all extracted HTML templates exist and contain markup."""
    expected_templates = [
        "layout.html",
        "login.html",
        "recs.html",
        "recs_category_card.html",
        "recs_book_row.html",
        "recs_empty_books_row.html",
        "recs_empty.html",
        "timetables_list.html",
        "timetables_date_row.html",
        "timetables_empty_row.html",
        "day_timetable.html",
        "day_event_row.html",
        "day_empty_events_row.html",
        "location_option.html",
        "alert.html",
    ]
    for tpl in expected_templates:
        path = os.path.join(TEMPLATES_DIR, tpl)
        assert os.path.isfile(path), f"Template file {tpl} not found"
        content = AdminTemplateRenderer.load_template(tpl)
        assert len(content.strip()) > 0, f"Template file {tpl} is empty"


def test_template_renderer_login_view():
    """Verify login page rendering with and without error alerts."""
    html_normal = AdminTemplateRenderer.render_login()
    assert "<form" in html_normal
    assert "BookTower Admin" in html_normal
    assert 'type="password"' in html_normal
    assert "alert alert-error" not in html_normal

    html_error = AdminTemplateRenderer.render_login(error="Неверный логин")
    assert "alert alert-error" in html_error
    assert "Неверный логин" in html_error


def test_template_renderer_recs_view():
    """Verify recommendations view rendering with categories, books, and empty states."""
    # Empty categories
    html_empty = AdminTemplateRenderer.render_recs([], message="Успешно сохранено")
    assert "Успешно сохранено" in html_empty
    assert "Категории рекомендаций отсутствуют" in html_empty

    # With categories and books
    book = Book(title="Война и мир", sold_by=["Стенд 1"], authors=["Лев Толстой"], description="Классика")
    cat = RecommendationCategory(name="Классика", books=[book])
    html_with_data = AdminTemplateRenderer.render_recs([cat], error="Ошибка загрузки")
    assert "Ошибка загрузки" in html_with_data
    assert "Война и мир" in html_with_data
    assert "Лев Толстой" in html_with_data
    assert "Стенд 1" in html_with_data


def test_template_renderer_timetables_view():
    """Verify timetables list and day views rendering."""
    # Timetables list
    html_list = AdminTemplateRenderer.render_timetables_list(["10092026", "11092026"])
    assert "10092026" in html_list
    assert "10.09.2026" in html_list
    assert "11092026" in html_list

    # Single day view
    event = Event(
        time="10:00",
        title="Лекция",
        location="Зал 1",
        description="Интересная лекция",
        participants=["Спикер 1"],
        organizer="Издательство",
    )
    day = DayTimetable(date="10092026", events=[event])
    html_day = AdminTemplateRenderer.render_day_timetable(
        date_key="10092026",
        timetable=day,
        all_locations=["Зал 1", "Зал 2"],
    )
    assert "Лекция" in html_day
    assert "Зал 1" in html_day
    assert "Спикер 1" in html_day
    assert 'value="Зал 2"' in html_day
    assert "locationSelect" in html_day


def test_date_and_time_validation():
    """Verify robust date and start time validation in AdminTimetableService."""
    # Date validation and normalization
    assert AdminTimetableService.validate_and_normalize_date("2026-09-14") == "14092026"
    assert AdminTimetableService.validate_and_normalize_date("14.09.2026") == "14092026"
    assert AdminTimetableService.validate_and_normalize_date("14092026") == "14092026"

    with pytest.raises(ValueError, match="Поле 'Дата' обязательно"):
        AdminTimetableService.validate_and_normalize_date("")

    with pytest.raises(ValueError, match="Некорректный формат даты"):
        AdminTimetableService.validate_and_normalize_date("invalid-date")

    # Start time validation
    assert AdminTimetableService.validate_time("10:00") == "10:00"
    assert AdminTimetableService.validate_time("9:30") == "09:30"
    assert AdminTimetableService.validate_time("14:45") == "14:45"

    with pytest.raises(ValueError, match="Поле 'Время' обязательно"):
        AdminTimetableService.validate_time("")

    with pytest.raises(ValueError, match="Некорректный формат времени"):
        AdminTimetableService.validate_time("25:00")


def test_router_event_add_with_start_time(temp_admin_env):
    """Verify adding event with start time."""
    config, _, _ = temp_admin_env
    router = AdminRouter(config=config)
    token = router.session_manager.create_session()
    cookie = f"{config.session_cookie_name}={token}"
    headers = {
        "Cookie": cookie,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    body = "time=11%3A00&title=Лекция+о+книгах&location_select=Главная+сцена".encode("utf-8")
    req = AdminRequest(method="POST", path="/timetables/10092026/events/add", headers=headers, body=body)
    resp = router.route(req)
    assert resp.status_code == 302

    timetable = router.timetable_service.get_day_timetable("10092026")
    assert len(timetable.events) == 2
    added_event = timetable.events[1]
    assert added_event.time == "11:00"
    assert added_event.title == "Лекция о книгах"


def test_recs_category_emoji_selection_and_update(temp_admin_env):
    """Verify choosing and changing emoji for recommendation categories."""
    config, recs_file, _ = temp_admin_env
    service = AdminRecsService(recs_file)

    # Add category with emoji
    service.add_category("Научпоп", emoji="🔬")
    cats = service.get_categories()
    assert len(cats) == 2
    assert cats[1].name == "Научпоп"
    assert cats[1].emoji == "🔬"

    # Update category emoji and name
    service.update_category(old_name="Научпоп", new_name="Наука и Космос", emoji="🚀")
    updated_cats = service.get_categories()
    assert updated_cats[1].name == "Наука и Космос"
    assert updated_cats[1].emoji == "🚀"

    # Render template with category emoji
    html = AdminTemplateRenderer.render_recs(updated_cats)
    assert "🚀 Наука и Космос" in html
    assert "editCat_Наука и Космос" in html
    assert "editEmoji_Наука и Космос" in html


def test_staged_changes_save_and_discard_flow(temp_admin_env):
    """Verify in-memory changes are not written immediately until saved or discarded."""
    config, recs_file, timetables_dir = temp_admin_env
    router = AdminRouter(config=config)
    token = router.session_manager.create_session()
    cookie = f"{config.session_cookie_name}={token}"
    headers = {
        "Cookie": cookie,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # 1. Stage a new category and timetable day
    body_cat = "category_name=Фантастика&emoji=🧙".encode("utf-8")
    router.route(AdminRequest(method="POST", path="/recs/category/add", headers=headers, body=body_cat))

    body_date = "date=15092026".encode("utf-8")
    router.route(AdminRequest(method="POST", path="/timetables/add", headers=headers, body=body_date))

    # Check that in-memory services show changes
    assert "Фантастика" in [c.name for c in router.recs_service.get_categories()]
    assert "15092026" in router.timetable_service.list_days()

    # BUT disk files are NOT updated yet!
    with open(recs_file, "r", encoding="utf-8") as f:
        disk_recs = json.load(f)
    assert "Фантастика" not in [c["rec"] for c in disk_recs["recs"]]
    assert not os.path.exists(os.path.join(timetables_dir, "15092026.json"))

    # 2. Discard changes
    resp_discard = router.route(AdminRequest(method="POST", path="/discard-changes", headers=headers))
    assert resp_discard.status_code == 302
    assert "Фантастика" not in [c.name for c in router.recs_service.get_categories()]
    assert "15092026" not in router.timetable_service.list_days()

    # 3. Stage again and Save changes
    router.route(AdminRequest(method="POST", path="/recs/category/add", headers=headers, body=body_cat))
    router.route(AdminRequest(method="POST", path="/timetables/add", headers=headers, body=body_date))

    resp_save = router.route(AdminRequest(method="POST", path="/save-changes", headers=headers))
    assert resp_save.status_code == 302

    # Now disk files MUST be updated!
    with open(recs_file, "r", encoding="utf-8") as f:
        disk_recs_after = json.load(f)
    assert "Фантастика" in [c["rec"] for c in disk_recs_after["recs"]]
    assert os.path.exists(os.path.join(timetables_dir, "15092026.json"))


def test_layout_bottom_buttons_and_dialog_confirmations():
    """Verify red save button and grey discard button with dialog confirmations exist in layout."""
    layout = AdminTemplateRenderer.load_template("layout.html")
    assert "Сохранить изменения и обновить бота" in layout
    assert "Отменить изменения" in layout
    assert "btn-danger" in layout
    assert "btn-secondary" in layout
    assert "confirm(" in layout


def test_no_placeholders_or_english_duplicates_in_templates():
    """Verify templates do not contain placeholders or repetitive English duplicate labels."""
    templates_to_check = [
        "layout.html",
        "login.html",
        "recs.html",
        "recs_category_card.html",
        "timetables_list.html",
        "day_timetable.html",
    ]
    for tpl in templates_to_check:
        content = AdminTemplateRenderer.load_template(tpl)
        assert 'placeholder=' not in content, f"Found placeholder in template {tpl}"
        assert '(Timetables)' not in content, f"Found '(Timetables)' in template {tpl}"
        assert '(Recs)' not in content, f"Found '(Recs)' in template {tpl}"
        assert '(Title)' not in content, f"Found '(Title)' in template {tpl}"
        assert '(Time)' not in content, f"Found '(Time)' in template {tpl}"
        assert '(Location)' not in content, f"Found '(Location)' in template {tpl}"
        assert '(Sold by)' not in content, f"Found '(Sold by)' in template {tpl}"


def test_sidebar_layout_rendered():
    """Verify left sidebar navigation is present in layout."""
    layout = AdminTemplateRenderer.load_template("layout.html")
    assert '<aside class="sidebar">' in layout
    assert '<main class="main-wrapper">' in layout


def test_emoji_picker_modal_in_layout():
    """Verify popup emoji picker modal with categories, search and complete emoji dataset without Russian flag."""
    layout = AdminTemplateRenderer.load_template("layout.html")
    assert 'id="emojiModalBackdrop"' in layout
    assert 'class="emoji-modal"' in layout
    assert 'id="emojiSearchInput"' in layout
    assert 'openEmojiPicker' in layout
    assert 'closeEmojiPicker' in layout
    assert 'EMOJI_DATA' in layout
    assert 'books' in layout
    assert 'smileys' in layout
    assert 'people' in layout
    assert 'animals' in layout
    assert 'food' in layout
    assert 'flags' in layout
    # Verify Russian flag is NOT in layout
    assert '🇷🇺' not in layout
    # Verify other world flags are present
    assert '🇺🇦' in layout
    assert '🇺🇸' in layout
    assert '🇬🇧' in layout
    assert '🇪🇺' in layout


def test_android_time_picker_and_default_at_10():
    """Verify Android Material TimePicker with 24-hour clock dial, default set to 10:00, and no AM/PM."""
    layout = AdminTemplateRenderer.load_template("layout.html")
    assert 'id="androidTimeModalBackdrop"' in layout
    assert 'android-time-modal' in layout
    assert 'id="timeClockFace"' in layout
    assert 'id="timeHourDisplay"' in layout
    assert 'id="timeMinuteDisplay"' in layout
    assert 'openAndroidTimePicker' in layout
    assert 'closeAndroidTimePicker' in layout
    assert 'confirmAndroidTimePicker' in layout
    assert 'pickerHour = 10' in layout

    tpl = AdminTemplateRenderer.load_template("day_timetable.html")
    assert 'openAndroidTimePicker' in tpl
    assert 'id="eventStartTime"' in tpl
    assert 'value="10:00"' in tpl
    assert '10:00' in tpl
    assert 'AM' not in tpl
    assert 'PM' not in tpl
