"""Comprehensive tests for data import and export (AdminDataTransferService, Web UI, and CLI)."""

import io
import json
import os
import shutil
import tempfile
import sqlite3
import zipfile
from unittest.mock import MagicMock, patch
import pytest

from admin.app import AdminApp
from admin.auth.authenticator import AdminAuthenticator
from admin.auth.session_manager import AdminSessionManager
from admin.config import AdminConfig
from admin.server.request import AdminRequest
from admin.server.response import AdminResponse
from admin.server.router import AdminRouter
from admin.services.data_service import AdminDataTransferService, VALID_COMPONENTS
from admin.__main__ import handle_export, handle_import, main as admin_main


@pytest.fixture
def sample_assets_dir():
    """Create a temporary assets directory with realistic data."""
    temp_dir = tempfile.mkdtemp()

    # db/
    db_dir = os.path.join(temp_dir, "db")
    os.makedirs(db_dir, exist_ok=True)
    with sqlite3.connect(os.path.join(db_dir, ".admin_users.db")) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS dummy (id INT)")
    with sqlite3.connect(os.path.join(db_dir, "wishlist.db")) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS dummy (id INT)")

    # map/
    map_dir = os.path.join(temp_dir, "map")
    os.makedirs(map_dir, exist_ok=True)
    with open(os.path.join(map_dir, "map.png"), "wb") as f:
        f.write(b"PNG_SAMPLE_MAP_BYTES")
    with open(os.path.join(map_dir, "active_map.json"), "w", encoding="utf-8") as f:
        json.dump({"active_map": "map.png"}, f)

    # participants/
    parts_dir = os.path.join(temp_dir, "participants")
    os.makedirs(parts_dir, exist_ok=True)
    with open(os.path.join(parts_dir, "participants.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "participants": [
                    {
                        "name": "Издательство Альпина",
                        "stand": "A-01",
                        "description": "Нон-фикшн книги",
                        "link": "https://alpina.ru",
                    }
                ]
            },
            f,
        )

    # recs/
    recs_dir = os.path.join(temp_dir, "recs")
    os.makedirs(recs_dir, exist_ok=True)
    with open(os.path.join(recs_dir, "recs.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "recs": [
                    {
                        "rec": "Художественная литература",
                        "emoji": "📚",
                        "books": [
                            {
                                "title": "Мастер и Маргарита",
                                "authors": ["Михаил Булгаков"],
                                "soldBy": ["Стенд 5"],
                                "description": "Классика",
                            }
                        ],
                    }
                ]
            },
            f,
        )

    # timetables/
    tt_dir = os.path.join(temp_dir, "timetables")
    os.makedirs(tt_dir, exist_ok=True)
    with open(os.path.join(tt_dir, "10092026.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "date": "10092026",
                "events": [
                    {
                        "time": "11:00",
                        "title": "Лекция о литературе",
                        "location": "Зал 1",
                        "description": "Интересная лекция",
                        "participants": ["Спикер 1"],
                        "organizer": "Организатор",
                        "is_children_activity": False,
                    }
                ],
            },
            f,
        )

    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestAdminDataTransferService:
    def test_export_to_bytes_and_file(self, sample_assets_dir):
        service = AdminDataTransferService(sample_assets_dir)

        # Export to bytes
        zip_bytes = service.export_assets_to_zip()
        assert isinstance(zip_bytes, bytes)
        assert len(zip_bytes) > 0

        # Verify zip content
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            namelist = zf.namelist()
            assert "db/.admin_users.db" not in namelist
            assert "db/wishlist.db" in namelist
            assert "map/map.png" in namelist
            assert "map/active_map.json" in namelist
            assert "participants/participants.json" in namelist
            assert "recs/recs.json" in namelist
            assert "timetables/10092026.json" in namelist

        # Export to file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            out_path = tf.name
        try:
            res_path = service.export_assets_to_zip(output_target=out_path)
            assert res_path == out_path
            assert os.path.exists(out_path)
            assert os.path.getsize(out_path) > 0
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

    def test_validate_zip_structure_valid(self, sample_assets_dir):
        service = AdminDataTransferService(sample_assets_dir)
        zip_bytes = service.export_assets_to_zip()

        val = service.validate_zip_structure(zip_bytes)
        assert val["is_valid"] is True
        assert set(val["components_found"]) == {"db", "map", "participants", "recs", "timetables"}

        # Partial validation for specific component
        val_recs = service.validate_zip_structure(zip_bytes, component="recs")
        assert val_recs["is_valid"] is True
        assert val_recs["target_component"] == "recs"

    def test_validate_zip_with_wrapper_root_folder(self, sample_assets_dir):
        """Verify zip files with a root 'assets/' or 'booktower/' wrapper folder are parsed cleanly."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("assets/recs/recs.json", json.dumps({"recs": []}))
            zf.writestr("assets/timetables/12092026.json", json.dumps({"date": "12092026", "events": []}))

        service = AdminDataTransferService(sample_assets_dir)
        val = service.validate_zip_structure(buf.getvalue())
        assert val["is_valid"] is True
        assert val["prefix"] == "assets/"
        assert "recs" in val["components_found"]
        assert "timetables" in val["components_found"]

    def test_validate_zip_invalid_archive(self, sample_assets_dir):
        service = AdminDataTransferService(sample_assets_dir)
        with pytest.raises(ValueError, match="Некорректный ZIP-архив"):
            service.validate_zip_structure(b"not a valid zip content")

    def test_validate_zip_path_traversal(self, sample_assets_dir):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../evil.txt", "malicious content")

        service = AdminDataTransferService(sample_assets_dir)
        with pytest.raises(ValueError, match="небезопасный путь"):
            service.validate_zip_structure(buf.getvalue())

    def test_validate_zip_invalid_json(self, sample_assets_dir):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("recs/recs.json", "this is not valid json")

        service = AdminDataTransferService(sample_assets_dir)
        with pytest.raises(ValueError, match="Ошибка в формате JSON"):
            service.validate_zip_structure(buf.getvalue())

    def test_validate_zip_missing_requested_component(self, sample_assets_dir):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("timetables/10092026.json", json.dumps({"date": "10092026", "events": []}))

        service = AdminDataTransferService(sample_assets_dir)
        with pytest.raises(ValueError, match="отсутствуют файлы для выбранного раздела 'recs'"):
            service.validate_zip_structure(buf.getvalue(), component="recs")

    def test_import_full_assets(self, sample_assets_dir):
        # Create a new custom zip with different content
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("recs/recs.json", json.dumps({"recs": [{"rec": "Новая категория", "books": []}]}))
            zf.writestr("timetables/20092026.json", json.dumps({"date": "20092026", "events": []}))
            zf.writestr("participants/participants.json", json.dumps({"participants": [{"name": "Новый участник", "stand": "B-99"}]}))
            zf.writestr("map/new_map.png", b"PNG_NEW_MAP")
            zf.writestr("db/test.db", b"DB_CONTENT")

        service = AdminDataTransferService(sample_assets_dir)
        result = service.import_assets_from_zip(buf.getvalue(), component="all")

        assert result["status"] == "ok"
        assert result["component"] == "all"
        assert len(result["imported_components"]) == 5

        # Verify filesystem updated
        with open(os.path.join(sample_assets_dir, "recs", "recs.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["recs"][0]["rec"] == "Новая категория"

        with open(os.path.join(sample_assets_dir, "timetables", "20092026.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["date"] == "20092026"

        assert not os.path.exists(os.path.join(sample_assets_dir, "timetables", "10092026.json"))

    def test_import_partial_component_only_updates_target(self, sample_assets_dir):
        # Create a zip containing new recs AND new timetables
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("recs/recs.json", json.dumps({"recs": [{"rec": "Только рекомендации", "books": []}]}))
            zf.writestr("timetables/99092026.json", json.dumps({"date": "99092026", "events": []}))

        service = AdminDataTransferService(sample_assets_dir)
        # Import ONLY recs
        result = service.import_assets_from_zip(buf.getvalue(), component="recs")

        assert result["status"] == "ok"
        assert result["component"] == "recs"
        assert result["imported_components"] == ["recs"]

        # Verify recs was updated
        with open(os.path.join(sample_assets_dir, "recs", "recs.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["recs"][0]["rec"] == "Только рекомендации"

        # Verify timetables was NOT modified (old timetable still exists, 99092026 was not imported)
        assert os.path.exists(os.path.join(sample_assets_dir, "timetables", "10092026.json"))
        assert not os.path.exists(os.path.join(sample_assets_dir, "timetables", "99092026.json"))

        # Verify participants, map, db were untouched
        assert os.path.exists(os.path.join(sample_assets_dir, "participants", "participants.json"))
        assert os.path.exists(os.path.join(sample_assets_dir, "map", "map.png"))
        assert os.path.exists(os.path.join(sample_assets_dir, "db", ".admin_users.db"))

    def test_import_multiple_selected_components(self, sample_assets_dir):
        # Create a zip containing new recs, participants, and timetables
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("recs/recs.json", json.dumps({"recs": [{"rec": "Multi Service Recs", "books": []}]}))
            zf.writestr("participants/participants.json", json.dumps({"participants": [{"name": "Multi Service Part", "stand": "S-1"}]}))
            zf.writestr("timetables/99092026.json", json.dumps({"date": "99092026", "events": []}))

        service = AdminDataTransferService(sample_assets_dir)
        # Import ONLY recs and participants
        result = service.import_assets_from_zip(buf.getvalue(), components=["recs", "participants"])

        assert result["status"] == "ok"
        assert set(result["imported_components"]) == {"recs", "participants"}

        # Verify recs and participants updated
        with open(os.path.join(sample_assets_dir, "recs", "recs.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["recs"][0]["rec"] == "Multi Service Recs"

        with open(os.path.join(sample_assets_dir, "participants", "participants.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["participants"][0]["name"] == "Multi Service Part"

        # Verify timetables was NOT updated (old timetable still exists)
        assert os.path.exists(os.path.join(sample_assets_dir, "timetables", "10092026.json"))
        assert not os.path.exists(os.path.join(sample_assets_dir, "timetables", "99092026.json"))


class TestAdminWebDataEndpoints:
    @pytest.fixture
    def app_router_with_session(self, sample_assets_dir):
        config = AdminConfig(
            host="127.0.0.1",
            port=0,
            auth_db_path=os.path.join(sample_assets_dir, "db", ".admin_users.db"),
            assets_path=sample_assets_dir,
            recs_path=os.path.join(sample_assets_dir, "recs", "recs.json"),
            timetables_path=os.path.join(sample_assets_dir, "timetables"),
            participants_path=os.path.join(sample_assets_dir, "participants", "participants.json"),
            map_dir=os.path.join(sample_assets_dir, "map"),
            map_path=os.path.join(sample_assets_dir, "map", "map.png"),
        )
        app = AdminApp(config)
        session_token = app.session_manager.create_session()
        headers = {"cookie": f"{config.session_cookie_name}={session_token}"}
        return app.router, headers, sample_assets_dir

    def test_get_data_page(self, app_router_with_session):
        router, headers, _ = app_router_with_session
        req = AdminRequest(method="GET", path="/data", headers=headers)
        resp = router.route(req)

        assert resp.status_code == 200
        html = resp.body.decode("utf-8")
        assert "Импорт и экспорт данных" in html
        assert "/data/export" in html
        assert "/data/import" in html
        assert 'class="active">💾 Экспорт / Импорт' in html
        # Verify select dropdown is replaced with checkboxes
        assert '<select name="component"' not in html
        assert 'type="checkbox"' in html
        assert 'name="components"' in html
        assert 'value="db"' in html
        assert 'value="map"' in html
        assert 'value="participants"' in html
        assert 'value="recs"' in html
        assert 'value="timetables"' in html
        assert "Выбрать все" in html
        assert "Снять все" in html

    def test_data_export_web_download(self, app_router_with_session):
        router, headers, _ = app_router_with_session
        req = AdminRequest(method="GET", path="/data/export", headers=headers)
        resp = router.route(req)

        assert resp.status_code == 200
        assert resp.headers.get("Content-Type") == "application/zip"
        assert "attachment; filename=" in resp.headers.get("Content-Disposition", "")

        # Verify valid zip payload
        with zipfile.ZipFile(io.BytesIO(resp.body), "r") as zf:
            assert "recs/recs.json" in zf.namelist()
            assert "timetables/10092026.json" in zf.namelist()

    def test_data_export_api_download(self, app_router_with_session):
        router, headers, _ = app_router_with_session
        req = AdminRequest(method="GET", path="/api/data/export", headers=headers)
        resp = router.route(req)

        assert resp.status_code == 200
        assert resp.headers.get("Content-Type") == "application/zip"
        with zipfile.ZipFile(io.BytesIO(resp.body), "r") as zf:
            assert "recs/recs.json" in zf.namelist()

    def test_post_data_import_web_form(self, app_router_with_session):
        router, headers, assets_dir = app_router_with_session

        # Prepare a zip to upload
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("recs/recs.json", json.dumps({"recs": [{"rec": "Web Import Category", "books": []}]}))

        # Construct multipart/form-data body
        boundary = "---------------------------974767299852498929531610575"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="component"\r\n\r\n'
            f"recs\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="zip_file"; filename="import.zip"\r\n'
            f"Content-Type: application/zip\r\n\r\n"
        ).encode("utf-8") + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode("utf-8")

        import_headers = dict(headers)
        import_headers["content-type"] = f"multipart/form-data; boundary={boundary}"

        req = AdminRequest(method="POST", path="/data/import", headers=import_headers, body=body)
        resp = router.route(req)

        assert resp.status_code == 302
        assert "/data?msg=" in resp.headers["Location"]

        # Check recs.json updated and service cache reloaded
        categories = router.recs_service.get_categories()
        assert len(categories) == 1
        assert categories[0].name == "Web Import Category"

    def test_post_data_import_multiple_checkboxes(self, app_router_with_session):
        router, headers, assets_dir = app_router_with_session

        # Prepare a zip with both recs and participants
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("recs/recs.json", json.dumps({"recs": [{"rec": "Multi Checkbox Rec", "books": []}]}))
            zf.writestr("participants/participants.json", json.dumps({"participants": [{"name": "Multi Checkbox Part", "stand": "M-1"}]}))

        boundary = "---------------------------974767299852498929531610575"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="components"\r\n\r\n'
            f"recs\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="components"\r\n\r\n'
            f"participants\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="zip_file"; filename="multi_import.zip"\r\n'
            f"Content-Type: application/zip\r\n\r\n"
        ).encode("utf-8") + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode("utf-8")

        import_headers = dict(headers)
        import_headers["content-type"] = f"multipart/form-data; boundary={boundary}"

        req = AdminRequest(method="POST", path="/data/import", headers=import_headers, body=body)
        resp = router.route(req)

        assert resp.status_code == 302
        assert "/data?msg=" in resp.headers["Location"]

        categories = router.recs_service.get_categories()
        assert any(c.name == "Multi Checkbox Rec" for c in categories)
        parts = router.participants_service.get_participants()
        assert any(p.name == "Multi Checkbox Part" for p in parts)

    def test_post_data_import_invalid_zip_redirects_with_error(self, app_router_with_session):
        router, headers, _ = app_router_with_session
        boundary = "---------------------------974767299852498929531610575"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="component"\r\n\r\n'
            f"recs\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="zip_file"; filename="corrupt.zip"\r\n'
            f"Content-Type: application/zip\r\n\r\n"
            f"INVALID_DATA\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        import_headers = dict(headers)
        import_headers["content-type"] = f"multipart/form-data; boundary={boundary}"

        req = AdminRequest(method="POST", path="/data/import", headers=import_headers, body=body)
        resp = router.route(req)

        assert resp.status_code == 302
        assert "/data?error=" in resp.headers["Location"]

    def test_api_data_import_json(self, app_router_with_session):
        router, headers, _ = app_router_with_session

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("participants/participants.json", json.dumps({"participants": [{"name": "API Participant", "stand": "Z-9"}]}))

        boundary = "---------------------------974767299852498929531610575"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="component"\r\n\r\n'
            f"participants\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="parts.zip"\r\n'
            f"Content-Type: application/zip\r\n\r\n"
        ).encode("utf-8") + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode("utf-8")

        api_headers = dict(headers)
        api_headers["content-type"] = f"multipart/form-data; boundary={boundary}"

        req = AdminRequest(method="POST", path="/api/data/import", headers=api_headers, body=body)
        resp = router.route(req)

        assert resp.status_code == 200
        data = json.loads(resp.body.decode("utf-8"))
        assert data["status"] == "ok"
        assert data["component"] == "participants"

    def test_api_data_import_multiple_components_json(self, app_router_with_session):
        router, headers, _ = app_router_with_session

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("recs/recs.json", json.dumps({"recs": [{"rec": "API Multi Rec", "books": []}]}))
            zf.writestr("participants/participants.json", json.dumps({"participants": [{"name": "API Multi Part", "stand": "P-1"}]}))

        boundary = "---------------------------974767299852498929531610575"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="components"\r\n\r\n'
            f"recs\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="components"\r\n\r\n'
            f"participants\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="multi.zip"\r\n'
            f"Content-Type: application/zip\r\n\r\n"
        ).encode("utf-8") + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode("utf-8")

        api_headers = dict(headers)
        api_headers["content-type"] = f"multipart/form-data; boundary={boundary}"

        req = AdminRequest(method="POST", path="/api/data/import", headers=api_headers, body=body)
        resp = router.route(req)

        assert resp.status_code == 200
        data = json.loads(resp.body.decode("utf-8"))
        assert data["status"] == "ok"
        assert "participants" in data["imported_components"]
        assert "recs" in data["imported_components"]


class TestAdminCLI:
    def test_cli_export_and_import_subcommands(self, sample_assets_dir):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            export_zip_path = tf.name

        try:
            # 1. Export via CLI subcommand
            with patch("sys.exit") as mock_exit:
                admin_main(["export", export_zip_path, "--assets-path", sample_assets_dir])
                mock_exit.assert_called_once_with(0)

            assert os.path.exists(export_zip_path)
            assert os.path.getsize(export_zip_path) > 0

            # 2. Modify one file in assets
            recs_file = os.path.join(sample_assets_dir, "recs", "recs.json")
            with open(recs_file, "w", encoding="utf-8") as f:
                json.dump({"recs": [{"rec": "Changed Category", "books": []}]}, f)

            # 3. Import back via CLI subcommand
            with patch("sys.exit") as mock_exit:
                admin_main(["import", export_zip_path, "--component", "recs", "--assets-path", sample_assets_dir])
                mock_exit.assert_called_once_with(0)

            # Verify restored
            with open(recs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                assert data["recs"][0]["rec"] == "Художественная литература"

            # 4. Import back multiple components via CLI
            with patch("sys.exit") as mock_exit:
                admin_main(["import", export_zip_path, "--component", "recs", "timetables", "--assets-path", sample_assets_dir])
                mock_exit.assert_called_once_with(0)

        finally:
            if os.path.exists(export_zip_path):
                os.remove(export_zip_path)

    def test_cli_export_and_import_flags(self, sample_assets_dir):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            export_zip_path = tf.name

        try:
            # Export via --export flag
            with patch("sys.exit") as mock_exit:
                admin_main(["--export", export_zip_path, "--assets-path", sample_assets_dir])
                mock_exit.assert_called_once_with(0)

            # Import via --import and --partial-import flags
            with patch("sys.exit") as mock_exit:
                admin_main(["--import", export_zip_path, "--partial-import", "timetables", "--assets-path", sample_assets_dir])
                mock_exit.assert_called_once_with(0)

        finally:
            if os.path.exists(export_zip_path):
                os.remove(export_zip_path)

    def test_cli_import_invalid_file(self, sample_assets_dir):
        with patch("sys.exit") as mock_exit:
            admin_main(["import", "non_existent_file.zip", "--assets-path", sample_assets_dir])
            mock_exit.assert_called_once_with(1)
