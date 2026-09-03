"""Comprehensive tests for the BookTower Admin Console."""

import json
import os
import shutil
import tempfile
import urllib.request
from typing import Dict
from unittest.mock import patch
import pytest

from admin.app import AdminApp
from admin.auth.authenticator import AdminAuthenticator
from admin.auth.session_manager import AdminSessionManager
from admin.config import AdminConfig
from admin.server.request import AdminRequest
from admin.server.response import AdminResponse
from admin.server.router import AdminRouter
from admin.services.map_service import AdminMapService
from admin.services.recs_service import AdminRecsService
from admin.services.timetable_service import AdminTimetableService
from admin.views.template_renderer import AdminTemplateRenderer, TEMPLATES_DIR
from bot.recommendations.book import Book
from bot.recommendations.category import RecommendationCategory
from bot.timetable.day import DayTimetable
from bot.timetable.event import Event


@pytest.fixture
def temp_admin_env():
    """Create a temporary directory with recs.json, timetables, and map for testing."""
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

    map_dir = os.path.join(temp_dir, "map")
    os.makedirs(map_dir, exist_ok=True)
    map_file = os.path.join(map_dir, "map.png")
    with open(map_file, "wb") as f:
        f.write(b"PNG_INITIAL_MAP_CONTENT")

    auth_db = os.path.join(temp_dir, "test_.admin_users.db")
    part_dir = os.path.join(temp_dir, "participants")
    os.makedirs(part_dir, exist_ok=True)
    part_file = os.path.join(part_dir, "participants.json")
    initial_parts = {
        "participants": [
            {
                "name": "Издательство МИФ",
                "stand": "10",
                "description": "Полезные книги",
                "link": "https://mif.ru",
            }
        ]
    }
    with open(part_file, "w", encoding="utf-8") as f:
        json.dump(initial_parts, f)

    config = AdminConfig(
        host="127.0.0.1",
        port=0,
        auth_db_path=auth_db,
        assets_path=temp_dir,
        recs_path=recs_file,
        timetables_path=timetables_dir,
        participants_path=part_file,
        map_dir=map_dir,
        map_path=map_file,
    )

    # Initialize auth and create confirmed test admin user
    auth = AdminAuthenticator(config=config, db_path=auth_db)
    auth.create_admin_user("testadmin", "testpassword", is_confirmed=True)

    yield config, recs_file, timetables_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


# --- Authentication & Session Tests ---

def test_authenticator(temp_admin_env):
    config, _, _ = temp_admin_env
    auth = AdminAuthenticator(config=config)

    assert auth.authenticate("testadmin", "testpassword") is True
    assert auth.authenticate("testadmin", "wrong") is False
    assert auth.authenticate("wrong", "testpassword") is False
    assert auth.authenticate("", "") is False
    assert auth.authenticate(None, None) is False


def test_authenticator_registration_and_approval(temp_admin_env):
    config, _, _ = temp_admin_env
    auth = AdminAuthenticator(config=config)

    # 1. Registration validation errors
    ok, err = auth.register("", "secret123")
    assert ok is False
    assert "cannot be empty" in err

    ok, err = auth.register("ab", "secret123")
    assert ok is False
    assert "at least 3 characters" in err

    ok, err = auth.register("user@bad#name", "secret123")
    assert ok is False
    assert "letters, numbers" in err

    ok, err = auth.register("newuser", "123")
    assert ok is False
    assert "at least 6 characters" in err

    # 2. Valid registration -> status is pending (unconfirmed)
    ok, msg = auth.register("newuser", "securepass123")
    assert ok is True
    assert "awaiting administrator approval" in msg

    # Cannot login while unconfirmed
    assert auth.authenticate("newuser", "securepass123") is False
    assert auth.is_confirmed("newuser") is False

    # Duplicate registration rejected
    ok, err = auth.register("newuser", "anotherpass123")
    assert ok is False
    assert "already exists" in err

    # 3. List pending users
    pending = auth.list_pending_users()
    assert any(u["username"] == "newuser" for u in pending)

    # 4. Approve user
    assert auth.approve_user("newuser") is True
    assert auth.is_confirmed("newuser") is True

    # Now login succeeds!
    assert auth.authenticate("newuser", "securepass123") is True
    assert auth.authenticate("newuser", "wrongpass") is False

    # 5. Reject / Delete user
    assert auth.reject_user("newuser") is True
    assert auth.user_exists("newuser") is False
    assert auth.authenticate("newuser", "securepass123") is False


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


def test_router_registration_and_pending_flow(temp_admin_env):
    """Verify web registration flow, password mismatch handling, and pending login feedback."""
    config, _, _ = temp_admin_env
    router = AdminRouter(config=config)

    # 1. GET /register returns registration HTML
    req_reg_get = AdminRequest(method="GET", path="/register", headers={})
    resp_reg_get = router.route(req_reg_get)
    assert resp_reg_get.status_code == 200
    assert "Регистрация нового администратора" in resp_reg_get.body.decode("utf-8")

    # 2. POST /register with mismatched passwords
    body_mismatch = b"username=candidate1&password=password123&confirm_password=password456"
    req_mismatch = AdminRequest(
        method="POST",
        path="/register",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=body_mismatch,
    )
    resp_mismatch = router.route(req_mismatch)
    assert resp_mismatch.status_code == 400
    assert "не совпадают" in resp_mismatch.body.decode("utf-8")

    # 3. POST /register successful
    body_ok = b"username=candidate1&password=password123&confirm_password=password123"
    req_ok = AdminRequest(
        method="POST",
        path="/register",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=body_ok,
    )
    resp_ok = router.route(req_ok)
    assert resp_ok.status_code == 200
    assert "Registration successful" in resp_ok.body.decode("utf-8") or "Регистрация успешна" in resp_ok.body.decode("utf-8")

    # 4. Attempt login with unconfirmed user
    body_login = b"username=candidate1&password=password123"
    req_login = AdminRequest(
        method="POST",
        path="/login",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=body_login,
    )
    resp_login = router.route(req_login)
    assert resp_login.status_code == 401
    assert "ожидает подтверждения" in resp_login.body.decode("utf-8")

    # 5. Confirm user via authenticator and verify login now succeeds
    router.authenticator.approve_user("candidate1")
    resp_login_ok = router.route(req_login)
    assert resp_login_ok.status_code == 302
    assert resp_login_ok.headers["Location"] == "/timetables"


def test_router_basic_auth_header(temp_admin_env):
    """Verify HTTP Basic Authentication header on protected endpoints."""
    import base64

    config, _, _ = temp_admin_env
    router = AdminRouter(config=config)

    # Valid credentials via Authorization header
    creds = base64.b64encode(b"testadmin:testpassword").decode("ascii")
    headers = {"Authorization": f"Basic {creds}"}

    req_api = AdminRequest(method="GET", path="/api/timetables", headers=headers)
    resp_api = router.route(req_api)
    assert resp_api.status_code == 200

    # Invalid credentials via Authorization header
    bad_creds = base64.b64encode(b"testadmin:wrongpass").decode("ascii")
    bad_headers = {"Authorization": f"Basic {bad_creds}"}
    req_bad = AdminRequest(method="GET", path="/api/timetables", headers=bad_headers)
    assert router.route(req_bad).status_code == 401


def test_auth_cli_and_bash_script(temp_admin_env):
    """Verify interactive one-by-one approval and clearing via CLI and bash script."""
    import subprocess
    from unittest.mock import patch
    from admin.auth.cli import main as cli_main

    config, _, _ = temp_admin_env
    auth = AdminAuthenticator(config=config)

    # 1. Register candidates for interactive review
    auth.register("cliadmin_yes", "secretpass999")
    auth.register("cliadmin_no", "secretpass888")
    assert auth.is_confirmed("cliadmin_yes") is False
    assert auth.is_confirmed("cliadmin_no") is False

    # Simulate interactive input: approve first ('y'), reject second ('n')
    with patch("builtins.input", side_effect=["y", "n"]):
        ret = cli_main(["--db-path", config.auth_db_path])
        assert ret == 0

    # First user is approved
    assert auth.is_confirmed("cliadmin_yes") is True
    assert auth.authenticate("cliadmin_yes", "secretpass999") is True

    # Second user was not approved and therefore deleted from the DB
    assert auth.user_exists("cliadmin_no") is False
    assert auth.authenticate("cliadmin_no", "secretpass888") is False

    # 2. Test bash script interactive execution with stdin
    auth.register("bash_approve", "pass_approve_1")
    auth.register("bash_decline", "pass_decline_2")
    assert auth.is_confirmed("bash_approve") is False
    assert auth.is_confirmed("bash_decline") is False

    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "auth_approval", "approveAdmins.sh")
    env = dict(os.environ, ADMIN_USERS_DB_PATH=config.auth_db_path)

    # Send 'y\nn\n' to bash script
    res = subprocess.run([script_path], input="y\nn\n", env=env, capture_output=True, text=True)
    assert res.returncode == 0
    assert "approved" in res.stdout.lower()
    assert "removed" in res.stdout.lower()

    # bash_approve should be confirmed
    assert auth.is_confirmed("bash_approve") is True
    assert auth.authenticate("bash_approve", "pass_approve_1") is True

    # bash_decline should be removed from database
    assert auth.user_exists("bash_decline") is False

    # 3. Test clearing non-approved users via bash script
    auth.register("unwanted1", "pass123456")
    auth.register("unwanted2", "pass654321")
    assert len(auth.list_pending_users()) == 2

    res_clear = subprocess.run([script_path, "--clear"], env=env, capture_output=True, text=True)
    assert res_clear.returncode == 0
    assert "cleared 2" in res_clear.stdout.lower()
    assert len(auth.list_pending_users()) == 0
    assert auth.user_exists("unwanted1") is False
    assert auth.user_exists("unwanted2") is False


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
        auth_db_path=config_base.auth_db_path,
        assets_path=config_base.assets_path,
        recs_path=config_base.recs_path,
        timetables_path=config_base.timetables_path,
    )
    auth = AdminAuthenticator(config=server_config)
    auth.create_admin_user("admin", "secretpassword", is_confirmed=True)

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
        "register.html",
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


def test_template_renderer_login_and_register_view():
    """Verify login and register page rendering with and without alerts."""
    html_login = AdminTemplateRenderer.render_login()
    assert "<form" in html_login
    assert "BookTower Admin" in html_login
    assert 'type="password"' in html_login
    assert "alert alert-error" not in html_login
    assert "/register" in html_login

    html_login_err = AdminTemplateRenderer.render_login(error="Неверный логин")
    assert "alert alert-error" in html_login_err
    assert "Неверный логин" in html_login_err

    html_register = AdminTemplateRenderer.render_register()
    assert "<form" in html_register
    assert "Регистрация нового администратора" in html_register
    assert "/login" in html_register
    assert "confirm_password" in html_register

    html_reg_ok = AdminTemplateRenderer.render_register(message="Регистрация успешна")
    assert "alert alert-success" in html_reg_ok
    assert "Регистрация успешна" in html_reg_ok


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
        is_children_activity=False,
    )
    kids_event = Event(
        time="11:30",
        title="Детский кукольный спектакль",
        location="Детский уголок",
        description="Спектакль для малышей",
        participants=["Кукловод"],
        organizer="Театр сказок",
        is_children_activity=True,
    )
    day = DayTimetable(date="10092026", events=[event, kids_event])
    html_day = AdminTemplateRenderer.render_day_timetable(
        date_key="10092026",
        timetable=day,
        all_locations=["Зал 1", "Зал 2", "Детский уголок"],
    )
    assert "Лекция" in html_day
    assert "Зал 1" in html_day
    assert "Спикер 1" in html_day
    assert "Детский кукольный спектакль" in html_day
    assert "Детская программа" in html_day
    assert "Основная программа" in html_day
    assert 'value="Зал 2"' in html_day
    assert "locationSelect" in html_day
    assert "is_children_activity" in html_day


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
    assert added_event.is_children_activity is False


def test_router_event_add_with_children_activity_flag(temp_admin_env):
    """Verify adding children activity event."""
    config, _, _ = temp_admin_env
    router = AdminRouter(config=config)
    token = router.session_manager.create_session()
    cookie = f"{config.session_cookie_name}={token}"
    headers = {
        "Cookie": cookie,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    body = "time=12%3A00&title=Детская+викторина&location_select=Детский+шатер&is_children_activity=1".encode("utf-8")
    req = AdminRequest(method="POST", path="/timetables/10092026/events/add", headers=headers, body=body)
    resp = router.route(req)
    assert resp.status_code == 302

    timetable = router.timetable_service.get_day_timetable("10092026")
    assert len(timetable.events) == 2
    added_event = timetable.events[1]
    assert added_event.time == "12:00"
    assert added_event.title == "Детская викторина"
    assert added_event.location == "Детский шатер"
    assert added_event.is_children_activity is True


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
        "register.html",
        "recs.html",
        "recs_category_card.html",
        "timetables_list.html",
        "day_timetable.html",
        "map.html",
        "map_version_row.html",
        "map_empty.html",
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
    assert '<a href="/map"' in layout


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


def test_admin_config_from_env_defaults_and_overrides():
    """Verify AdminConfig.from_env loads all environment variables correctly."""
    with patch.dict(os.environ, {}, clear=True):
        cfg = AdminConfig.from_env()
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8080
        assert cfg.session_cookie_name == "booktower_admin_session"
        assert cfg.session_timeout_seconds == 86400
        assert cfg.auth_db_path.endswith("assets/db/.admin_users.db")
        assert cfg.map_dir.endswith("assets/map")
        assert cfg.map_path.endswith("assets/map/map.png")

    custom_env = {
        "ADMIN_HOST": "127.0.0.1",
        "ADMIN_PORT": "9000",
        "ADMIN_USERS_DB_PATH": "custom/auth.db",
        "ADMIN_SESSION_COOKIE_NAME": "custom_cookie",
        "ADMIN_SESSION_TIMEOUT_SECONDS": "7200",
        "ASSETS_PATH": "custom_assets",
        "RECS_PATH": "custom_assets/recs.json",
        "TIMETABLES_PATH": "custom_assets/timetables",
        "MAP_DIR": "custom_assets/map",
        "MAP_PATH": "custom_assets/map/custom_map.png",
    }
    with patch.dict(os.environ, custom_env, clear=True):
        cfg = AdminConfig.from_env()
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 9000
        assert cfg.auth_db_path.endswith("custom/auth.db")
        assert os.path.isabs(cfg.auth_db_path)
        assert cfg.session_cookie_name == "custom_cookie"
        assert cfg.session_timeout_seconds == 7200
        assert cfg.assets_path.endswith("custom_assets")
        assert cfg.recs_path.endswith("custom_assets/recs.json")
        assert cfg.timetables_path.endswith("custom_assets/timetables")
        assert cfg.map_dir.endswith("custom_assets/map")
        assert cfg.map_path.endswith("custom_assets/map/custom_map.png")


def test_authenticator_anchored_to_project_root_regardless_of_cwd(tmp_path):
    """Verify AdminAuthenticator resolves relative paths consistently regardless of CWD."""
    orig_cwd = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        auth = AdminAuthenticator()
        assert os.path.isabs(auth.db_path)
        assert "assets/db/.admin_users.db" in auth.db_path
        assert not auth.db_path.startswith(str(tmp_path))
    finally:
        os.chdir(orig_cwd)


# --- Map Service & Router Tests ---

def test_map_service_upload_versioning_and_selection(tmp_path):
    map_dir = str(tmp_path / "map")
    service = AdminMapService(map_dir)

    # Initial state
    assert service.list_maps() == []
    assert service.get_active_map() is None
    assert service.get_active_map_path() is None

    # 1. Upload first map version (active by default)
    map1_name = service.upload_map("floor1.png", b"MAP_V1_PNG_DATA", set_as_active=True)
    assert map1_name == "floor1.png"
    assert service.get_active_map() == "floor1.png"
    assert service.has_pending_changes() is True

    # 2. Upload second map version without setting active
    map2_name = service.upload_map("floor2.png", b"MAP_V2_PNG_DATA", set_as_active=False)
    assert map2_name == "floor2.png"
    assert service.get_active_map() == "floor1.png"

    # List maps shows both versions, with active map first
    maps = service.list_maps()
    assert len(maps) == 2
    assert maps[0]["filename"] == "floor1.png"
    assert maps[0]["is_active"] is True
    assert maps[1]["filename"] == "floor2.png"
    assert maps[1]["is_active"] is False

    # 3. Select second map as active
    service.select_map("floor2.png")
    assert service.get_active_map() == "floor2.png"

    # 4. Save to disk
    service.save_to_disk()
    assert service.has_pending_changes() is False
    with open(os.path.join(map_dir, "active_map.json"), "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta.get("active_map") == "floor2.png"
    # map.png is NOT created as an extra file
    assert not os.path.exists(os.path.join(map_dir, "map.png"))

    # 5. Selecting non-existent map raises ValueError
    with pytest.raises(ValueError, match="не найден"):
        service.select_map("non_existent.png")

    # 6. Deleting active map raises ValueError
    with pytest.raises(ValueError, match="Нельзя удалить активную карту"):
        service.delete_map("floor2.png")

    # 7. Delete non-active map version
    assert service.delete_map("floor1.png") is True
    service.save_to_disk()
    remaining = service.list_maps()
    assert len(remaining) == 1  # only floor2.png
    assert "floor1.png" not in [m["filename"] for m in remaining]


def test_map_service_upload_validation(tmp_path):
    map_dir = str(tmp_path / "map")
    service = AdminMapService(map_dir)

    # Empty content
    with pytest.raises(ValueError, match="не может быть пустым"):
        service.upload_map("test.png", b"")

    # Invalid extension
    with pytest.raises(ValueError, match="Неподдерживаемый формат"):
        service.upload_map("test.exe", b"binary")


def test_admin_request_multipart_parsing():
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="set_active"\r\n\r\n'
        "1\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="map_file"; filename="venue_plan.png"\r\n'
        "Content-Type: image/png\r\n\r\n"
        "FAKE_IMAGE_BYTES_123\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = AdminRequest(
        method="POST",
        path="/map/upload",
        headers={
            "content-type": f"multipart/form-data; boundary={boundary}",
            "content-length": str(len(body)),
        },
        body=body,
    )

    assert req.form_data.get("set_active") == "1"
    assert "map_file" in req.files
    assert req.files["map_file"]["filename"] == "venue_plan.png"
    assert req.files["map_file"]["content"] == b"FAKE_IMAGE_BYTES_123"
    assert req.files["map_file"]["content_type"] == "image/png"


def test_admin_map_routes(temp_admin_env):
    config, _, _ = temp_admin_env
    auth = AdminAuthenticator(config=config)
    session_mgr = AdminSessionManager()
    token = session_mgr.create_session()
    cookie_hdr = f"{config.session_cookie_name}={token}"

    map_service = AdminMapService(config.map_dir)
    router = AdminRouter(config=config, authenticator=auth, session_manager=session_mgr, map_service=map_service)

    # 1. GET /map page
    req = AdminRequest("GET", "/map", headers={"cookie": cookie_hdr})
    resp = router.route(req)
    assert resp.status_code == 200
    html = resp.body.decode("utf-8")
    assert "Управление картой ярмарки" in html
    assert "Загрузить новую карту" in html
    assert "map.png" in html

    # 2. POST /map/upload via multipart request
    boundary = "TestBoundary123"
    upload_body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="set_active"\r\n\r\n'
        "1\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="map_file"; filename="festival_map_2026.png"\r\n'
        "Content-Type: image/png\r\n\r\n"
        "TEST_IMAGE_PAYLOAD\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = AdminRequest(
        "POST",
        "/map/upload",
        headers={
            "cookie": cookie_hdr,
            "content-type": f"multipart/form-data; boundary={boundary}",
        },
        body=upload_body,
    )
    resp = router.route(req)
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/map?msg=")

    assert map_service.get_active_map() == "festival_map_2026.png"

    # 3. GET /map/file/festival_map_2026.png preview
    req = AdminRequest("GET", "/map/file/festival_map_2026.png", headers={"cookie": cookie_hdr})
    resp = router.route(req)
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "image/png"
    assert resp.body == b"TEST_IMAGE_PAYLOAD"

    # 4. POST /map/select
    req = AdminRequest(
        "POST",
        "/map/select",
        headers={"cookie": cookie_hdr, "content-type": "application/x-www-form-urlencoded"},
        body=b"filename=map.png",
    )
    resp = router.route(req)
    assert resp.status_code == 302
    assert map_service.get_active_map() == "map.png"

    # 5. POST /map/delete
    req = AdminRequest(
        "POST",
        "/map/delete",
        headers={"cookie": cookie_hdr, "content-type": "application/x-www-form-urlencoded"},
        body=b"filename=festival_map_2026.png",
    )
    resp = router.route(req)
    assert resp.status_code == 302

    # 6. JSON API endpoints
    # GET /api/map
    req = AdminRequest("GET", "/api/map", headers={"cookie": cookie_hdr})
    resp = router.route(req)
    assert resp.status_code == 200
    api_data = json.loads(resp.body.decode("utf-8"))
    assert "active_map" in api_data
    assert "maps" in api_data

    # POST /api/map/select
    req = AdminRequest(
        "POST",
        "/api/map/select",
        headers={"cookie": cookie_hdr, "content-type": "application/json"},
        body=json.dumps({"filename": "map.png"}).encode("utf-8"),
    )
    resp = router.route(req)
    assert resp.status_code == 200
    api_resp = json.loads(resp.body.decode("utf-8"))
    assert api_resp["status"] == "ok"


def test_unsaved_changes_notification_when_changes_staged(temp_admin_env):
    """Verify that when changes are staged in admin, a warning banner informs the user that changes won't be shown in the bot until uploaded."""
    config, _, _ = temp_admin_env
    router = AdminRouter(config=config)
    token = router.session_manager.create_session()
    cookie_hdr = f"{config.session_cookie_name}={token}"
    headers = {
        "Cookie": cookie_hdr,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # Initially no unsaved changes
    assert not router.has_unsaved_changes()
    resp = router.route(AdminRequest("GET", "/timetables", headers={"Cookie": cookie_hdr}))
    html = resp.body.decode("utf-8")
    assert "Есть несохраненные изменения" not in html

    # 1. Stage a recommendation change
    body_cat = "category_name=Новинки&emoji=✨".encode("utf-8")
    router.route(AdminRequest("POST", "/recs/category/add", headers=headers, body=body_cat))

    assert router.has_unsaved_changes()

    # Verify unsaved changes banner appears on all views
    for path in ["/timetables", "/recs", "/map"]:
        resp = router.route(AdminRequest("GET", path, headers={"Cookie": cookie_hdr}))
        html = resp.body.decode("utf-8")
        assert "Есть несохраненные изменения" in html
        assert "не будут отображаться в боте" in html
        assert "Сохранить изменения и обновить бота" in html

    # 2. Discard changes -> banner disappears
    router.route(AdminRequest("POST", "/discard-changes", headers=headers))
    assert not router.has_unsaved_changes()

    resp = router.route(AdminRequest("GET", "/recs", headers={"Cookie": cookie_hdr}))
    html = resp.body.decode("utf-8")
    assert "Есть несохраненные изменения" not in html

    # 3. Stage a timetable change
    body_date = "date=16092026".encode("utf-8")
    router.route(AdminRequest("POST", "/timetables/add", headers=headers, body=body_date))
    assert router.has_unsaved_changes()

    resp_day = router.route(AdminRequest("GET", "/timetables/16092026", headers={"Cookie": cookie_hdr}))
    html_day = resp_day.body.decode("utf-8")
    assert "Есть несохраненные изменения" in html_day
    assert "не будут отображаться в боте" in html_day

    # 4. Save changes -> banner disappears
    router.route(AdminRequest("POST", "/save-changes", headers=headers))
    assert not router.has_unsaved_changes()

    resp_after = router.route(AdminRequest("GET", "/timetables", headers={"Cookie": cookie_hdr}))
    html_after = resp_after.body.decode("utf-8")
    assert "Есть несохраненные изменения" not in html_after


def test_admin_save_changes_redirect_preserves_page(temp_admin_env):
    config, _, _ = temp_admin_env
    auth = AdminAuthenticator(config=config)
    session_mgr = AdminSessionManager()
    token = session_mgr.create_session()
    cookie_hdr = f"{config.session_cookie_name}={token}"
    router = AdminRouter(config=config, authenticator=auth, session_manager=session_mgr)

    # 1. Save from /map using Referer header
    req = AdminRequest(
        "POST",
        "/save-changes",
        headers={"Cookie": cookie_hdr, "Referer": "http://localhost:8000/map"},
    )
    resp = router.route(req)
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/map?msg=")

    # 2. Save from /map using lowercase referer header
    req = AdminRequest(
        "POST",
        "/save",
        headers={"Cookie": cookie_hdr, "referer": "http://localhost:8000/map"},
    )
    resp = router.route(req)
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/map?msg=")

    # 3. Save from /map using return_to form field
    req = AdminRequest(
        "POST",
        "/save-changes",
        headers={"Cookie": cookie_hdr, "Content-Type": "application/x-www-form-urlencoded"},
        body=b"return_to=%2Fmap",
    )
    resp = router.route(req)
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/map?msg=")

    # 4. Save from day timetable using return_to
    req = AdminRequest(
        "POST",
        "/save-changes",
        headers={"Cookie": cookie_hdr, "Content-Type": "application/x-www-form-urlencoded"},
        body=b"return_to=%2Ftimetables%2F11092026",
    )
    resp = router.route(req)
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/timetables/11092026?msg=")

    # 5. Discard from /map using return_to
    req = AdminRequest(
        "POST",
        "/discard-changes",
        headers={"Cookie": cookie_hdr, "Content-Type": "application/x-www-form-urlencoded"},
        body=b"return_to=%2Fmap",
    )
    resp = router.route(req)
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/map?msg=")


def test_beforeunload_script_in_layout():
    """Verify beforeunload listener and form input tracking script exists in layout template."""
    layout = AdminTemplateRenderer.load_template("layout.html")
    assert "beforeunload" in layout
    assert "hasUnsubmittedFormInputs" in layout
    assert "isFormSubmitting" in layout
    assert "{{ unsaved_changes_banner }}" in layout
    assert "selectedIndex" in layout
    assert "defaultIdx" in layout


def test_admin_timetable_sorting_and_toggle(temp_admin_env):
    """Verify AdminTimetableService sorts events by time then name, and supports toggle_children."""
    _, _, timetables_dir = temp_admin_env
    service = AdminTimetableService(timetables_dir)

    service.create_day("20092026")
    service.add_event("20092026", time="15:00", title="Вечерняя лекция", location="Зал 1")
    service.add_event("20092026", time="10:00", title="Презентация книги", location="Зал 1")
    service.add_event("20092026", time="10:00", title="Автограф-сессия", location="Зал 2")
    service.add_event("20092026", time="09:30", title="Открытие", location="Главная сцена")

    day_dict = service.get_day_dict("20092026")
    events = day_dict["events"]
    assert [e["time"] for e in events] == ["09:30", "10:00", "10:00", "15:00"]
    assert [e["title"] for e in events] == ["Открытие", "Автограф-сессия", "Презентация книги", "Вечерняя лекция"]

    # Toggle children activity for index 1 ("Автограф-сессия")
    assert events[1]["is_children_activity"] is False
    res = service.toggle_event_children_activity("20092026", 1)
    assert res is True
    assert service.get_day_dict("20092026")["events"][1]["is_children_activity"] is True

    # Toggle back
    res2 = service.toggle_event_children_activity("20092026", 1)
    assert res2 is False
    assert service.get_day_dict("20092026")["events"][1]["is_children_activity"] is False


def test_admin_day_timetable_rendering_and_edit_modal(temp_admin_env):
    """Verify render_day_timetable includes editable checkbox, edit buttons and edit modal markup."""
    _, _, timetables_dir = temp_admin_env
    service = AdminTimetableService(timetables_dir)
    service.create_day("21092026")
    service.add_event(
        "21092026",
        time="11:00",
        title="Детские сказки",
        location="Детский уголок",
        organizer="Изд. Сказка",
        participants=["Сказкач 1"],
        description="Чтение для детей",
        is_children_activity=True,
    )
    service.add_event(
        "21092026",
        time="14:00",
        title="Взрослая дискуссия",
        location="Конференц-зал",
        is_children_activity=False,
    )

    day = service.get_day_timetable("21092026")
    html = AdminTemplateRenderer.render_day_timetable(
        date_key="21092026",
        timetable=day,
        all_locations=["Детский уголок", "Конференц-зал"],
    )

    assert "/timetables/21092026/events/toggle_children" in html
    assert "checked" in html
    assert "✏️ Редактировать" in html
    assert "openEditEventModal" in html
    assert 'id="editEventModalBackdrop"' in html
    assert "/timetables/21092026/events/update" in html
    assert 'data-title="Детские сказки"' in html
    assert 'data-location="Детский уголок"' in html
    assert "Детская программа" in html


def test_admin_router_toggle_and_edit_events(temp_admin_env):
    """Verify router handles event toggle_children and event update routes."""
    config, _, timetables_dir = temp_admin_env
    router = AdminRouter(config=config)
    token = router.session_manager.create_session()
    cookie_hdr = f"{config.session_cookie_name}={token}"

    # Create day and add event
    router.timetable_service.create_day("22092026")
    router.timetable_service.add_event("22092026", time="10:00", title="Утренний воркшоп", location="Зал А")

    # 1. Toggle children activity via POST
    req_toggle = AdminRequest(
        method="POST",
        path="/timetables/22092026/events/toggle_children",
        headers={"Cookie": cookie_hdr, "Content-Type": "application/x-www-form-urlencoded"},
        body=b"event_index=0",
    )
    resp_toggle = router.route(req_toggle)
    assert resp_toggle.status_code == 302
    assert resp_toggle.headers["Location"] == "/timetables/22092026"
    assert router.timetable_service.get_day_dict("22092026")["events"][0]["is_children_activity"] is True

    # 2. Update event via POST
    req_update = AdminRequest(
        method="POST",
        path="/timetables/22092026/events/update",
        headers={"Cookie": cookie_hdr, "Content-Type": "application/x-www-form-urlencoded"},
        body=b"event_index=0&time=11%3A30&title=%D0%9E%D0%B1%D0%BD%D0%BE%D0%B2%D0%BB%D0%B5%D0%BD%D0%BD%D1%8B%D0%B9+%D0%B2%D0%BE%D1%80%D0%BA%D1%88%D0%BE%D0%BF&location=%D0%9D%D0%BE%D0%B2%D1%8B%D0%B9+%D0%B7%D0%B0%D0%BB&is_children_activity=0",
    )
    resp_update = router.route(req_update)
    assert resp_update.status_code == 302
    assert resp_update.headers["Location"].startswith("/timetables/22092026?msg=")

    updated_event = router.timetable_service.get_day_dict("22092026")["events"][0]
    assert updated_event["time"] == "11:30"
    assert updated_event["title"] == "Обновленный воркшоп"
    assert updated_event["location"] == "Новый зал"
    assert updated_event["is_children_activity"] is False


def test_admin_router_participants_crud_and_api(temp_admin_env):
    """Verify router handles participants web and API routes."""
    config, _, _ = temp_admin_env
    router = AdminRouter(config=config)
    token = router.session_manager.create_session()
    cookie_hdr = f"{config.session_cookie_name}={token}"
    headers_form = {"Cookie": cookie_hdr, "Content-Type": "application/x-www-form-urlencoded"}
    headers_json = {"Cookie": cookie_hdr, "Content-Type": "application/json"}

    # 1. GET /participants HTML view
    req_view = AdminRequest(method="GET", path="/participants", headers={"Cookie": cookie_hdr})
    resp_view = router.route(req_view)
    assert resp_view.status_code == 200
    html_content = resp_view.body.decode("utf-8")
    assert "Управление участниками и стендами" in html_content
    assert "Издательство МИФ" in html_content
    assert "10" in html_content

    # 2. POST /participants/add
    req_add_invalid = AdminRequest(
        method="POST",
        path="/participants/add",
        headers=headers_form,
        body=b"name=%D0%90%D0%BB%D1%8C%D0%BF%D0%B8%D0%BD%D0%B0&stand=2&link=bad_url&description=%D0%9A%D0%BD%D0%B8%D0%B3%D0%B8",
    )
    resp_add_invalid = router.route(req_add_invalid)
    assert resp_add_invalid.status_code == 302
    assert "error=" in resp_add_invalid.headers["Location"]

    req_add = AdminRequest(
        method="POST",
        path="/participants/add",
        headers=headers_form,
        body=b"name=%D0%90%D0%BB%D1%8C%D0%BF%D0%B8%D0%BD%D0%B0&stand=2&link=https%3A%2F%2Falpina.ru&description=%D0%9A%D0%BD%D0%B8%D0%B3%D0%B8",
    )
    resp_add = router.route(req_add)
    assert resp_add.status_code == 302
    assert resp_add.headers["Location"].startswith("/participants?msg=")
    assert router.has_unsaved_changes()

    # Verify sorting: Альпина (stand 2) comes before МИФ (stand 10)
    parts = router.participants_service.get_participants()
    assert len(parts) == 2
    assert parts[0].name == "Альпина"
    assert parts[0].stand == "2"

    # 3. POST /participants/update
    req_update = AdminRequest(
        method="POST",
        path="/participants/update",
        headers=headers_form,
        body=b"participant_index=0&name=%D0%90%D0%BB%D1%8C%D0%BF%D0%B8%D0%BD%D0%B0+%D0%9F%D0%B0%D0%B1%D0%BB%D0%B8%D1%88%D0%B5%D1%80&stand=1&link=https%3A%2F%2Falpina.ru&description=%D0%91%D0%B8%D0%B7%D0%BD%D0%B5%D1%81",
    )
    resp_update = router.route(req_update)
    assert resp_update.status_code == 302
    assert router.participants_service.get_participants()[0].name == "Альпина Паблишер"
    assert router.participants_service.get_participants()[0].stand == "1"

    # 4. POST /participants/delete
    req_delete = AdminRequest(
        method="POST",
        path="/participants/delete",
        headers=headers_form,
        body=b"participant_index=1",
    )
    resp_delete = router.route(req_delete)
    assert resp_delete.status_code == 302
    assert len(router.participants_service.get_participants()) == 1

    # 5. Global /discard-changes
    req_discard = AdminRequest(method="POST", path="/discard-changes", headers=headers_form)
    resp_discard = router.route(req_discard)
    assert resp_discard.status_code == 302
    assert not router.has_unsaved_changes()
    assert len(router.participants_service.get_participants()) == 1
    assert router.participants_service.get_participants()[0].name == "Издательство МИФ"

    # 6. API GET /api/participants
    req_api_get = AdminRequest(method="GET", path="/api/participants", headers=headers_json)
    resp_api_get = router.route(req_api_get)
    assert resp_api_get.status_code == 200
    api_get_data = json.loads(resp_api_get.body.decode("utf-8"))
    assert "participants" in api_get_data

    # 7. API POST /api/participants/add
    req_api_add = AdminRequest(
        method="POST",
        path="/api/participants/add",
        headers=headers_json,
        body=json.dumps({"name": "Самокат", "stand": "A-1", "link": "https://samokat.ru"}).encode("utf-8"),
    )
    resp_api_add = router.route(req_api_add)
    assert resp_api_add.status_code == 201
    assert len(router.participants_service.get_participants()) == 2

    # 8. API POST /api/save
    req_api_save = AdminRequest(method="POST", path="/api/save", headers=headers_json)
    resp_api_save = router.route(req_api_save)
    assert resp_api_save.status_code == 200
    assert not router.has_unsaved_changes()
