"""Tests for Admin Console LLM Import UI and API endpoints."""

import json
from unittest.mock import MagicMock, patch
import pytest

from admin.auth.authenticator import AdminAuthenticator
from admin.auth.session_manager import AdminSessionManager
from admin.config import AdminConfig
from admin.server.request import AdminRequest
from admin.server.response import AdminResponse
from admin.server.router import AdminRouter
from admin.services.map_service import AdminMapService
from admin.services.participants_service import AdminParticipantsService
from admin.services.recs_service import AdminRecsService
from admin.services.timetable_service import AdminTimetableService
from admin.views.template_renderer import AdminTemplateRenderer
from bot.recommendations.category import RecommendationCategory
from bot.timetable.day import DayTimetable


def test_llm_import_button_in_all_templates():
    """Verify 'Сгенерировать из внешнего источника' button is present across participants, timetables, and recs."""
    # Participants
    rendered_part = AdminTemplateRenderer.render_participants([])
    assert "Сгенерировать из внешнего источника" in rendered_part
    assert "openLlmImportModal('participants')" in rendered_part

    # Recommendations
    rendered_recs = AdminTemplateRenderer.render_recs([])
    assert "Сгенерировать из внешнего источника" in rendered_recs
    assert "openLlmImportModal('recommendations')" in rendered_recs

    # Timetables list
    rendered_tt_list = AdminTemplateRenderer.render_timetables_list([])
    assert "Сгенерировать из внешнего источника" in rendered_tt_list
    assert "openLlmImportModal('timetables')" in rendered_tt_list

    # Day timetable
    empty_day = DayTimetable.from_dict({"date": "10092026", "events": []})
    rendered_day = AdminTemplateRenderer.render_day_timetable("10092026", empty_day, [])
    assert "Сгенерировать из внешнего источника" in rendered_day
    assert "openLlmImportModal('timetables', '10092026')" in rendered_day


def test_llm_import_modal_markup_and_scripts_in_layout():
    """Verify modal dialog, working indicator text, and abort button exist in layout."""
    layout = AdminTemplateRenderer.load_template("layout.html")

    assert 'id="llmImportModalBackdrop"' in layout
    assert 'id="llmFileInput"' in layout
    assert 'id="llmUrlInput"' in layout
    assert 'id="llmWorkingText"' in layout
    assert 'id="llmAbortBtn"' in layout
    assert 'abortLlmImport' in layout
    assert 'openLlmImportModal' in layout
    assert 'handleLlmImportSubmit' in layout
    assert 'AbortController' in layout


@pytest.fixture
def test_router(tmp_path):
    recs_dir = tmp_path / "recs"
    recs_dir.mkdir(parents=True, exist_ok=True)
    recs_file = recs_dir / "recs.json"
    recs_file.write_text(json.dumps({"recs": []}), encoding="utf-8")

    tt_dir = tmp_path / "timetables"
    tt_dir.mkdir(parents=True, exist_ok=True)
    day_file = tt_dir / "10092026.json"
    day_file.write_text(json.dumps({"date": "10092026", "events": []}), encoding="utf-8")

    part_dir = tmp_path / "participants"
    part_dir.mkdir(parents=True, exist_ok=True)
    part_file = part_dir / "participants.json"
    part_file.write_text(json.dumps({"participants": []}), encoding="utf-8")

    map_dir = tmp_path / "map"
    map_dir.mkdir(parents=True, exist_ok=True)

    auth_db = str(tmp_path / "auth.db")

    cfg = AdminConfig(
        host="127.0.0.1",
        port=0,
        auth_db_path=auth_db,
        assets_path=str(tmp_path),
        recs_path=str(recs_file),
        timetables_path=str(tt_dir),
        participants_path=str(part_file),
        map_dir=str(map_dir),
        map_path=str(map_dir / "map.png"),
    )

    auth = AdminAuthenticator(config=cfg, db_path=auth_db)
    auth.create_admin_user("testadmin", "testpassword", is_confirmed=True)
    sess = AdminSessionManager(timeout_seconds=3600)

    recs_svc = AdminRecsService(str(recs_file))
    tt_svc = AdminTimetableService(str(tt_dir))
    map_svc = AdminMapService(str(map_dir))
    part_svc = AdminParticipantsService(str(part_file))

    router = AdminRouter(
        config=cfg,
        authenticator=auth,
        session_manager=sess,
        recs_service=recs_svc,
        timetable_service=tt_svc,
        map_service=map_svc,
        participants_service=part_svc,
    )
    return router, sess


def test_llm_import_api_requires_auth(test_router):
    router, _ = test_router
    req = AdminRequest(
        method="POST",
        path="/api/llm/load",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"entity": "participants", "url": "https://example.com"}).encode("utf-8"),
    )
    resp = router.route(req)
    assert resp.status_code == 401


@patch("admin.llm.transfer_to_json.LLMJsonConverter.from_url")
def test_llm_import_participants_from_url(mock_from_url, test_router):
    router, sess = test_router
    token = sess.create_session()
    cookie_header = f"booktower_admin_session={token}"

    mock_from_url.return_value = json.dumps({
        "participants": [
            {
                "name": "Новое Издательство",
                "stand": "42",
                "link": "https://newpub.com",
                "description": "Классика и современность",
            }
        ]
    })

    req = AdminRequest(
        method="POST",
        path="/api/llm/load",
        headers={
            "Content-Type": "application/json",
            "Cookie": cookie_header,
        },
        body=json.dumps({
            "entity": "participants",
            "url": "https://example.com/participants-list",
        }).encode("utf-8"),
    )
    resp = router.route(req)
    assert resp.status_code == 200
    data = json.loads(resp.body.decode("utf-8"))
    assert data["status"] == "ok"
    assert data["count"] == 1

    # Verify staged participants
    assert router.participants_service.has_pending_changes() is True
    parts = router.participants_service.get_participants()
    new_p = next((p for p in parts if p.stand == "42"), None)
    assert new_p is not None
    assert new_p.name == "Новое Издательство"
    assert new_p.link == "https://newpub.com"

    mock_from_url.assert_called_once_with("https://example.com/participants-list", "participants")


@patch("admin.llm.transfer_to_json.LLMJsonConverter.transfer_to_json")
def test_llm_import_participants_from_file_upload(mock_transfer, test_router):
    router, sess = test_router
    token = sess.create_session()
    cookie_header = f"booktower_admin_session={token}"

    mock_transfer.return_value = json.dumps({
        "participants": [
            {
                "name": "Альпина Паблишер",
                "stand": "55",
                "link": "alpina.ru",
                "description": "Нон-фикшн литература",
            }
        ]
    })

    boundary = "----WebKitFormBoundaryTest7MA4YWxkTrZu0gW"
    body_parts = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="entity"\r\n\r\n'
        "participants\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="publishers.csv"\r\n'
        "Content-Type: text/csv\r\n\r\n"
        "stand,name,link\r\n55,Альпина Паблишер,alpina.ru\r\n"
        f"--{boundary}--\r\n"
    )

    req = AdminRequest(
        method="POST",
        path="/api/llm/load",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Cookie": cookie_header,
        },
        body=body_parts.encode("utf-8"),
    )
    resp = router.route(req)
    assert resp.status_code == 200

    parts = router.participants_service.get_participants()
    alpina = next((p for p in parts if p.stand == "55"), None)
    assert alpina is not None
    assert alpina.name == "Альпина Паблишер"


@patch("admin.llm.transfer_to_json.LLMJsonConverter.from_url")
def test_llm_import_recommendations(mock_from_url, test_router):
    router, sess = test_router
    token = sess.create_session()
    cookie_header = f"booktower_admin_session={token}"

    mock_from_url.return_value = json.dumps({
        "recs": [
            {
                "rec": "Научная фантастика",
                "emoji": "🚀",
                "books": [
                    {
                        "title": "Солярис",
                        "description": "Классика фантастики",
                        "authors": ["Станислав Лем"],
                        "soldBy": ["Стенд 10"],
                    }
                ],
            }
        ]
    })

    req = AdminRequest(
        method="POST",
        path="/api/llm/load",
        headers={
            "Content-Type": "application/json",
            "Cookie": cookie_header,
        },
        body=json.dumps({
            "entity": "recommendations",
            "url": "https://example.com/books",
        }).encode("utf-8"),
    )
    resp = router.route(req)
    assert resp.status_code == 200

    assert router.recs_service.has_pending_changes() is True
    cats = router.recs_service.get_categories()
    sci_fi = next((c for c in cats if c.name == "Научная фантастика"), None)
    assert sci_fi is not None
    assert sci_fi.emoji == "🚀"
    assert len(sci_fi.books) == 1
    assert sci_fi.books[0].title == "Солярис"


@patch("admin.llm.transfer_to_json.LLMJsonConverter.transfer_to_json")
def test_llm_import_timetable_events(mock_transfer, test_router):
    router, sess = test_router
    token = sess.create_session()
    cookie_header = f"booktower_admin_session={token}"

    mock_transfer.return_value = json.dumps({
        "date": "10092026",
        "events": [
            {
                "time": "12:00",
                "title": "Презентация книги",
                "location": "Зал А",
                "description": "Встреча с автором",
                "participants": ["Автор", "Модератор"],
                "organizer": "Издательство",
                "is_children_activity": False,
            }
        ],
    })

    req = AdminRequest(
        method="POST",
        path="/api/llm/load",
        headers={
            "Content-Type": "application/json",
            "Cookie": cookie_header,
        },
        body=json.dumps({
            "entity": "timetables",
            "date": "10092026",
            "content": "12:00 Презентация книги в Зале А",
        }).encode("utf-8"),
    )
    resp = router.route(req)
    assert resp.status_code == 200

    assert router.timetable_service.has_pending_changes() is True
    day = router.timetable_service.get_day_timetable("10092026")
    assert day is not None
    pres = next((e for e in day.events if e.title == "Презентация книги"), None)
    assert pres is not None
    assert pres.time == "12:00"
    assert pres.location == "Зал А"


def test_llm_import_error_handling(test_router):
    router, sess = test_router
    token = sess.create_session()
    cookie_header = f"booktower_admin_session={token}"

    # Unknown entity
    req1 = AdminRequest(
        method="POST",
        path="/api/llm/load",
        headers={"Content-Type": "application/json", "Cookie": cookie_header},
        body=json.dumps({"entity": "unknown_entity", "url": "https://example.com"}).encode("utf-8"),
    )
    resp1 = router.route(req1)
    assert resp1.status_code == 400
    assert "Неизвестный тип сущности" in json.loads(resp1.body.decode("utf-8"))["error"]

    # Missing file and URL
    req2 = AdminRequest(
        method="POST",
        path="/api/llm/load",
        headers={"Content-Type": "application/json", "Cookie": cookie_header},
        body=json.dumps({"entity": "participants"}).encode("utf-8"),
    )
    resp2 = router.route(req2)
    assert resp2.status_code == 400
    assert "Не предоставлен файл или URL" in json.loads(resp2.body.decode("utf-8"))["error"]


@patch("admin.llm.transfer_to_json.LLMJsonConverter.from_url")
def test_llm_import_staged_lifecycle_edit_and_save(mock_from_url, test_router):
    """Test full lifecycle: import via LLM -> manual modification -> save to disk."""
    router, sess = test_router
    token = sess.create_session()
    cookie_header = f"booktower_admin_session={token}"

    mock_from_url.return_value = json.dumps({
        "participants": [
            {
                "name": "Издательство Эксмо",
                "stand": "77",
                "link": "eksmo.ru",
                "description": "Крупное издательство",
            }
        ]
    })

    # 1. Import via LLM
    req = AdminRequest(
        method="POST",
        path="/api/llm/load",
        headers={"Content-Type": "application/json", "Cookie": cookie_header},
        body=json.dumps({"entity": "participants", "url": "https://example.com"}).encode("utf-8"),
    )
    resp = router.route(req)
    assert resp.status_code == 200
    assert router.has_unsaved_changes() is True

    # 2. User modifies the imported participant as if added by hand
    parts = router.participants_service.get_participants()
    idx = next(i for i, p in enumerate(parts) if p.stand == "77")
    update_req = AdminRequest(
        method="POST",
        path="/participants/update",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cookie": cookie_header},
        body=f"participant_index={idx}&name=Эксмо+АСТ&stand=77&link=https%3A%2F%2Feksmo.ru&description=Холдинг".encode("utf-8"),
    )
    update_resp = router.route(update_req)
    assert update_resp.status_code == 302

    updated_part = router.participants_service.get_participants()[idx]
    assert updated_part.name == "Эксмо АСТ"

    # 3. User saves all changes to disk
    save_req = AdminRequest(
        method="POST",
        path="/save-changes",
        headers={"Cookie": cookie_header},
    )
    save_resp = router.route(save_req)
    assert save_resp.status_code == 302
    assert router.has_unsaved_changes() is False

    # Verify written to disk
    with open(router.config.participants_path, "r", encoding="utf-8") as f:
        disk_data = json.load(f)
    assert any(p["name"] == "Эксмо АСТ" for p in disk_data["participants"])


@patch("admin.llm.transfer_to_json.LLMJsonConverter.from_url")
def test_llm_import_staged_lifecycle_discard(mock_from_url, test_router):
    """Test lifecycle: import via LLM -> discard changes -> disk remains untouched."""
    router, sess = test_router
    token = sess.create_session()
    cookie_header = f"booktower_admin_session={token}"

    mock_from_url.return_value = json.dumps({
        "participants": [
            {
                "name": "Временный Участник",
                "stand": "999",
            }
        ]
    })

    # Import
    req = AdminRequest(
        method="POST",
        path="/api/llm/load",
        headers={"Content-Type": "application/json", "Cookie": cookie_header},
        body=json.dumps({"entity": "participants", "url": "https://example.com"}).encode("utf-8"),
    )
    router.route(req)
    assert router.has_unsaved_changes() is True

    # Discard
    discard_req = AdminRequest(
        method="POST",
        path="/discard-changes",
        headers={"Cookie": cookie_header},
    )
    discard_resp = router.route(discard_req)
    assert discard_resp.status_code == 302
    assert router.has_unsaved_changes() is False

    # Verify not on disk
    with open(router.config.participants_path, "r", encoding="utf-8") as f:
        disk_data = json.load(f)
    assert not any(p["stand"] == "999" for p in disk_data["participants"])


def test_admin_http_handler_broken_pipe_suppressed():
    """Verify AdminHttpHandler safely suppresses BrokenPipeError, ConnectionResetError, and OSError(32)."""
    from admin.server.handler import AdminHttpHandler

    class DummyHandler(AdminHttpHandler):
        def __init__(self):
            self.headers = {"Content-Length": "0"}
            self.rfile = MagicMock()
            self.rfile.read.return_value = b""
            self.wfile = MagicMock()
            self.path = "/test"
            self.router = MagicMock()

        def send_response(self, *args, **kwargs):
            pass

        def send_header(self, *args, **kwargs):
            pass

        def end_headers(self, *args, **kwargs):
            pass

    # 1. Test BrokenPipeError during _process_request
    handler = DummyHandler()
    handler.router.route.return_value = AdminResponse(body=b"payload", status_code=200)
    handler.wfile.write.side_effect = BrokenPipeError(32, "Broken pipe")
    # Should not raise
    handler._process_request("POST")

    # 2. Test ConnectionResetError during _process_request
    handler.wfile.write.side_effect = ConnectionResetError(104, "Connection reset")
    handler._process_request("POST")

    # 3. Test OSError(32) during _process_request
    err = OSError()
    err.errno = 32
    handler.wfile.write.side_effect = err
    handler._process_request("POST")

    # 4. Test handle() method catches BrokenPipeError
    with patch("http.server.BaseHTTPRequestHandler.handle", side_effect=BrokenPipeError(32, "Broken pipe")):
        handler.handle()

    with patch("http.server.BaseHTTPRequestHandler.handle", side_effect=ConnectionResetError(104, "Connection reset")):
        handler.handle()
