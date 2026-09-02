"""Request router dispatching endpoints and enforcing auth middleware."""

from typing import Optional
from urllib.parse import quote, urlparse

from admin.auth.authenticator import AdminAuthenticator
from admin.auth.session_manager import AdminSessionManager
from admin.config import AdminConfig
from admin.server.request import AdminRequest
from admin.server.response import AdminResponse
from admin.services.map_service import AdminMapService
from admin.services.recs_service import AdminRecsService
from admin.services.timetable_service import AdminTimetableService
from admin.views.template_renderer import AdminTemplateRenderer


class AdminRouter:
    """Dispatches incoming requests to handlers and manages authorization."""

    def __init__(
        self,
        config: Optional[AdminConfig] = None,
        authenticator: Optional[AdminAuthenticator] = None,
        session_manager: Optional[AdminSessionManager] = None,
        recs_service: Optional[AdminRecsService] = None,
        timetable_service: Optional[AdminTimetableService] = None,
        map_service: Optional[AdminMapService] = None,
    ):
        self.config = config or AdminConfig.from_env()
        self.authenticator = authenticator or AdminAuthenticator(self.config)
        self.session_manager = session_manager or AdminSessionManager(self.config.session_timeout_seconds)
        self.recs_service = recs_service or AdminRecsService(self.config.recs_path)
        self.timetable_service = timetable_service or AdminTimetableService(self.config.timetables_path)
        self.map_service = map_service or AdminMapService(self.config.map_dir)

    def route(self, request: AdminRequest) -> AdminResponse:
        """Route request to the appropriate handler."""
        path = request.path.rstrip("/")
        if not path:
            path = "/"

        # Public authentication and registration routes
        if path == "/login":
            if request.method == "GET":
                return self._handle_get_login(request)
            if request.method == "POST":
                return self._handle_post_login(request)

        if path == "/register":
            if request.method == "GET":
                return self._handle_get_register(request)
            if request.method == "POST":
                return self._handle_post_register(request)

        if path == "/logout":
            return self._handle_logout(request)

        # Authentication guard for protected routes (supports Session Cookie & HTTP Basic Auth)
        token = request.get_cookie(self.config.session_cookie_name)
        is_authenticated = self.session_manager.is_valid_session(token)

        if not is_authenticated:
            basic_creds = request.get_basic_auth()
            if basic_creds:
                u, p = basic_creds
                if self.authenticator.authenticate(u, p):
                    is_authenticated = True

        if not is_authenticated:
            if path.startswith("/api/"):
                return AdminResponse.unauthorized("Authentication required", as_json=True)
            return AdminResponse.redirect("/login")

        # Root redirect
        if path == "/":
            return AdminResponse.redirect("/timetables")

        # Global Save / Discard Staged Changes
        if path in ("/save-changes", "/save") and request.method == "POST":
            return self._handle_post_save_changes(request)
        if path in ("/discard-changes", "/discard", "/cancel-changes") and request.method == "POST":
            return self._handle_post_discard_changes(request)

        # Recommendations Web Routes
        if path == "/recs":
            return self._handle_get_recs(request)
        if path == "/recs/category/add" and request.method == "POST":
            return self._handle_post_recs_category_add(request)
        if path == "/recs/category/rename" and request.method == "POST":
            return self._handle_post_recs_category_rename(request)
        if path == "/recs/category/update" and request.method == "POST":
            return self._handle_post_recs_category_update(request)
        if path == "/recs/category/delete" and request.method == "POST":
            return self._handle_post_recs_category_delete(request)
        if path == "/recs/book/add" and request.method == "POST":
            return self._handle_post_recs_book_add(request)
        if path == "/recs/book/update" and request.method == "POST":
            return self._handle_post_recs_book_update(request)
        if path == "/recs/book/delete" and request.method == "POST":
            return self._handle_post_recs_book_delete(request)

        # Timetables Web Routes
        if path == "/timetables":
            return self._handle_get_timetables_list(request)
        if path == "/timetables/add" and request.method == "POST":
            return self._handle_post_timetables_add(request)
        if path == "/timetables/delete" and request.method == "POST":
            return self._handle_post_timetables_delete(request)

        # Map Web Routes
        if path == "/map":
            return self._handle_get_map(request)
        if path == "/map/upload" and request.method == "POST":
            return self._handle_post_map_upload(request)
        if path == "/map/select" and request.method == "POST":
            return self._handle_post_map_select(request)
        if path == "/map/delete" and request.method == "POST":
            return self._handle_post_map_delete(request)
        if path.startswith("/map/file/"):
            filename = path[len("/map/file/"):]
            return self._handle_get_map_file(request, filename)
        if path.startswith("/map/preview/"):
            filename = path[len("/map/preview/"):]
            return self._handle_get_map_file(request, filename)

        # Dynamic timetable day routes
        if path.startswith("/timetables/"):
            subpath = path[len("/timetables/"):]
            parts = subpath.split("/")
            date_key = parts[0]

            if len(parts) == 1:
                return self._handle_get_day_timetable(request, date_key)
            if len(parts) == 3 and parts[1] == "events":
                action = parts[2]
                if action == "add" and request.method == "POST":
                    return self._handle_post_day_event_add(request, date_key)
                if action == "update" and request.method == "POST":
                    return self._handle_post_day_event_update(request, date_key)
                if action == "delete" and request.method == "POST":
                    return self._handle_post_day_event_delete(request, date_key)
                if action in ("toggle_children", "toggle_children_activity") and request.method == "POST":
                    return self._handle_post_day_event_toggle_children(request, date_key)

        # JSON API Routes
        if path.startswith("/api/"):
            return self._route_api(request, path)

        return AdminResponse.html("<h1>404 Not Found</h1>", status_code=404)

    # --- Authentication & Registration Handlers ---

    def _handle_get_login(self, request: AdminRequest) -> AdminResponse:
        token = request.get_cookie(self.config.session_cookie_name)
        if self.session_manager.is_valid_session(token):
            return AdminResponse.redirect("/timetables")
        message = request.query_params.get("msg")
        error = request.query_params.get("error")
        html = AdminTemplateRenderer.render_login(error=error, message=message)
        return AdminResponse.html(html)

    def _handle_post_login(self, request: AdminRequest) -> AdminResponse:
        username = request.form_data.get("username", "")
        password = request.form_data.get("password", "")

        if self.authenticator.authenticate(username, password):
            token = self.session_manager.create_session()
            cookie_header = f"{self.config.session_cookie_name}={token}; Path=/; HttpOnly; SameSite=Lax"
            return AdminResponse.redirect("/timetables", cookies=[cookie_header])

        if self.authenticator.user_exists(username) and not self.authenticator.is_confirmed(username):
            error_msg = "Учетная запись ожидает подтверждения администратором"
        else:
            error_msg = "Неверное имя пользователя или пароль"

        html = AdminTemplateRenderer.render_login(error=error_msg)
        return AdminResponse.html(html, status_code=401)

    def _handle_get_register(self, request: AdminRequest) -> AdminResponse:
        token = request.get_cookie(self.config.session_cookie_name)
        if self.session_manager.is_valid_session(token):
            return AdminResponse.redirect("/timetables")
        message = request.query_params.get("msg")
        error = request.query_params.get("error")
        html = AdminTemplateRenderer.render_register(error=error, message=message)
        return AdminResponse.html(html)

    def _handle_post_register(self, request: AdminRequest) -> AdminResponse:
        username = request.form_data.get("username", "")
        password = request.form_data.get("password", "")
        confirm_password = request.form_data.get("confirm_password", "")

        if confirm_password and password != confirm_password:
            html = AdminTemplateRenderer.render_register(error="Введенные пароли не совпадают")
            return AdminResponse.html(html, status_code=400)

        success, message = self.authenticator.register(username, password)
        if success:
            html = AdminTemplateRenderer.render_register(message=message)
            return AdminResponse.html(html, status_code=200)

        html = AdminTemplateRenderer.render_register(error=message)
        return AdminResponse.html(html, status_code=400)

    def _handle_logout(self, request: AdminRequest) -> AdminResponse:
        token = request.get_cookie(self.config.session_cookie_name)
        self.session_manager.revoke_session(token)
        cookie_header = f"{self.config.session_cookie_name}=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT"
        return AdminResponse.redirect("/login", cookies=[cookie_header])

    # --- Staged Changes Handlers ---

    def _resolve_redirect_target(self, request: AdminRequest, default: str = "/timetables") -> str:
        """Determine safe redirect target after saving or discarding changes."""
        # 1. Check form field return_to
        return_to = request.form_data.get("return_to", "").strip()
        if return_to and return_to.startswith("/") and not return_to.startswith("//"):
            return return_to.split("?")[0]

        # 2. Check Referer header (case-insensitive)
        referer = request.headers.get("referer", "") or request.headers.get("Referer", "")
        if referer:
            try:
                parsed = urlparse(referer)
                clean_path = parsed.path.rstrip("/")
                if clean_path and clean_path.startswith("/") and not clean_path.startswith("//"):
                    return clean_path
            except Exception:
                pass

        return default

    def _handle_post_save_changes(self, request: AdminRequest) -> AdminResponse:
        redirect_target = self._resolve_redirect_target(request)
        try:
            self.recs_service.save_to_disk()
            self.timetable_service.save_to_disk()
            self.map_service.save_to_disk()
            return AdminResponse.redirect(redirect_target + "?msg=" + quote("Все изменения сохранены и информация бота обновлена!"))
        except Exception as e:
            return AdminResponse.redirect(redirect_target + "?error=" + quote(str(e)))

    def _handle_post_discard_changes(self, request: AdminRequest) -> AdminResponse:
        redirect_target = self._resolve_redirect_target(request)
        try:
            self.recs_service.discard_changes()
            self.timetable_service.discard_changes()
            self.map_service.discard_changes()
            return AdminResponse.redirect(redirect_target + "?msg=" + quote("Все несохраненные изменения отменены"))
        except Exception as e:
            return AdminResponse.redirect(redirect_target + "?error=" + quote(str(e)))

    def has_unsaved_changes(self) -> bool:
        """Check whether any admin service has uncommitted staged changes."""
        return bool(
            self.recs_service.has_pending_changes()
            or self.timetable_service.has_pending_changes()
            or self.map_service.has_pending_changes()
        )

    # --- Recommendations Web Handlers ---

    def _handle_get_recs(self, request: AdminRequest) -> AdminResponse:
        categories = self.recs_service.get_categories()
        error = request.query_params.get("error")
        message = request.query_params.get("msg")
        html = AdminTemplateRenderer.render_recs(
            categories,
            error=error,
            message=message,
            has_unsaved_changes=self.has_unsaved_changes(),
        )
        return AdminResponse.html(html)

    def _handle_post_recs_category_add(self, request: AdminRequest) -> AdminResponse:
        category_name = request.form_data.get("category_name", "")
        emoji = request.form_data.get("emoji", "")
        try:
            self.recs_service.add_category(category_name, emoji=emoji)
            return AdminResponse.redirect("/recs?msg=" + quote(f"Категория «{category_name}» успешно создана"))
        except Exception as e:
            return AdminResponse.redirect("/recs?error=" + quote(str(e)))

    def _handle_post_recs_category_update(self, request: AdminRequest) -> AdminResponse:
        old_name = request.form_data.get("old_name", "")
        new_name = request.form_data.get("new_name", old_name)
        emoji = request.form_data.get("emoji", "")
        try:
            self.recs_service.update_category(old_name=old_name, new_name=new_name, emoji=emoji)
            return AdminResponse.redirect("/recs?msg=" + quote(f"Категория «{new_name}» обновлена"))
        except Exception as e:
            return AdminResponse.redirect("/recs?error=" + quote(str(e)))

    def _handle_post_recs_category_rename(self, request: AdminRequest) -> AdminResponse:
        old_name = request.form_data.get("old_name", "")
        new_name = request.form_data.get("new_name", "")
        emoji = request.form_data.get("emoji", None)
        try:
            self.recs_service.rename_category(old_name, new_name, emoji=emoji)
            return AdminResponse.redirect("/recs?msg=" + quote("Категория переименована"))
        except Exception as e:
            return AdminResponse.redirect("/recs?error=" + quote(str(e)))

    def _handle_post_recs_category_delete(self, request: AdminRequest) -> AdminResponse:
        category_name = request.form_data.get("category_name", "")
        try:
            self.recs_service.delete_category(category_name)
            return AdminResponse.redirect("/recs?msg=" + quote(f"Категория «{category_name}» удалена"))
        except Exception as e:
            return AdminResponse.redirect("/recs?error=" + quote(str(e)))

    def _handle_post_recs_book_add(self, request: AdminRequest) -> AdminResponse:
        category_name = request.form_data.get("category_name", "")
        title = request.form_data.get("title", "")
        sold_by = request.form_data.get("sold_by", "")
        authors = request.form_data.get("authors", "")
        description = request.form_data.get("description", "")

        try:
            self.recs_service.add_book(
                category_name=category_name,
                title=title,
                sold_by=sold_by,
                description=description,
                authors=authors,
            )
            return AdminResponse.redirect("/recs?msg=" + quote(f"Книга «{title}» добавлена"))
        except Exception as e:
            return AdminResponse.redirect("/recs?error=" + quote(str(e)))

    def _handle_post_recs_book_update(self, request: AdminRequest) -> AdminResponse:
        category_name = request.form_data.get("category_name", "")
        index_str = request.form_data.get("book_index", "0")
        title = request.form_data.get("title", "")
        sold_by = request.form_data.get("sold_by", "")
        authors = request.form_data.get("authors", "")
        description = request.form_data.get("description", "")

        try:
            book_index = int(index_str)
            self.recs_service.update_book(
                category_name=category_name,
                book_index=book_index,
                title=title,
                sold_by=sold_by,
                description=description,
                authors=authors,
            )
            return AdminResponse.redirect("/recs?msg=" + quote("Книга обновлена"))
        except Exception as e:
            return AdminResponse.redirect("/recs?error=" + quote(str(e)))

    def _handle_post_recs_book_delete(self, request: AdminRequest) -> AdminResponse:
        category_name = request.form_data.get("category_name", "")
        index_str = request.form_data.get("book_index", "0")
        try:
            book_index = int(index_str)
            self.recs_service.delete_book(category_name, book_index)
            return AdminResponse.redirect("/recs?msg=" + quote("Книга удалена"))
        except Exception as e:
            return AdminResponse.redirect("/recs?error=" + quote(str(e)))

    # --- Timetables Web Handlers ---

    def _handle_get_timetables_list(self, request: AdminRequest) -> AdminResponse:
        dates = self.timetable_service.list_days()
        error = request.query_params.get("error")
        message = request.query_params.get("msg")
        html = AdminTemplateRenderer.render_timetables_list(
            dates,
            error=error,
            message=message,
            has_unsaved_changes=self.has_unsaved_changes(),
        )
        return AdminResponse.html(html)

    def _handle_post_timetables_add(self, request: AdminRequest) -> AdminResponse:
        date = request.form_data.get("date", "")
        try:
            created_date = self.timetable_service.create_day(date)
            return AdminResponse.redirect(f"/timetables/{created_date}?msg=" + quote(f"Расписание для {created_date} создано"))
        except Exception as e:
            return AdminResponse.redirect("/timetables?error=" + quote(str(e)))

    def _handle_post_timetables_delete(self, request: AdminRequest) -> AdminResponse:
        date = request.form_data.get("date", "")
        try:
            self.timetable_service.delete_day(date)
            return AdminResponse.redirect("/timetables?msg=" + quote(f"Расписание для {date} удалено"))
        except Exception as e:
            return AdminResponse.redirect("/timetables?error=" + quote(str(e)))

    def _handle_get_day_timetable(self, request: AdminRequest, date_key: str) -> AdminResponse:
        timetable = self.timetable_service.get_day_timetable(date_key)
        if not timetable:
            return AdminResponse.redirect("/timetables?error=" + quote(f"День {date_key} не найден"))

        all_locations = self.timetable_service.get_all_locations()
        error = request.query_params.get("error")
        message = request.query_params.get("msg")
        html = AdminTemplateRenderer.render_day_timetable(
            date_key=date_key,
            timetable=timetable,
            all_locations=all_locations,
            error=error,
            message=message,
            has_unsaved_changes=self.has_unsaved_changes(),
        )
        return AdminResponse.html(html)

    def _handle_post_day_event_add(self, request: AdminRequest, date_key: str) -> AdminResponse:
        time = request.form_data.get("time", "").strip()
        if not time:
            start_time = request.form_data.get("start_time", "").strip()
            end_time = request.form_data.get("end_time", "").strip()
            if start_time and end_time:
                time = f"{start_time} - {end_time}"
            elif start_time:
                time = start_time

        title = request.form_data.get("title", "")
        location_select = request.form_data.get("location_select", "")
        custom_location = request.form_data.get("custom_location", "")
        direct_location = request.form_data.get("location", "")

        location = custom_location if location_select == "__NEW__" else (location_select or direct_location)

        organizer = request.form_data.get("organizer", "")
        participants = request.form_data.get("participants", "")
        description = request.form_data.get("description", "")
        raw_children = request.form_data.get("is_children_activity", "0")
        is_children_activity = str(raw_children).strip().lower() in ("1", "true", "yes", "on")

        try:
            self.timetable_service.add_event(
                date=date_key,
                time=time,
                title=title,
                location=location,
                description=description,
                participants=participants,
                organizer=organizer,
                is_children_activity=is_children_activity,
            )
            return AdminResponse.redirect(f"/timetables/{date_key}?msg=" + quote(f"Мероприятие «{title}» добавлено"))
        except Exception as e:
            return AdminResponse.redirect(f"/timetables/{date_key}?error=" + quote(str(e)))

    def _handle_post_day_event_update(self, request: AdminRequest, date_key: str) -> AdminResponse:
        index_str = request.form_data.get("event_index", "0")
        time = request.form_data.get("time", "").strip()
        if not time:
            start_time = request.form_data.get("start_time", "").strip()
            end_time = request.form_data.get("end_time", "").strip()
            if start_time and end_time:
                time = f"{start_time} - {end_time}"
            elif start_time:
                time = start_time

        title = request.form_data.get("title", "")
        location_select = request.form_data.get("location_select", "")
        custom_location = request.form_data.get("custom_location", "")
        direct_location = request.form_data.get("location", "")

        location = custom_location if location_select == "__NEW__" else (location_select or direct_location)

        organizer = request.form_data.get("organizer", "")
        participants = request.form_data.get("participants", "")
        description = request.form_data.get("description", "")
        raw_children = request.form_data.get("is_children_activity", "0")
        is_children_activity = str(raw_children).strip().lower() in ("1", "true", "yes", "on")

        try:
            event_index = int(index_str)
            self.timetable_service.update_event(
                date=date_key,
                event_index=event_index,
                time=time,
                title=title,
                location=location,
                description=description,
                participants=participants,
                organizer=organizer,
                is_children_activity=is_children_activity,
            )
            return AdminResponse.redirect(f"/timetables/{date_key}?msg=" + quote("Мероприятие обновлено"))
        except Exception as e:
            return AdminResponse.redirect(f"/timetables/{date_key}?error=" + quote(str(e)))

    def _handle_post_day_event_delete(self, request: AdminRequest, date_key: str) -> AdminResponse:
        index_str = request.form_data.get("event_index", "0")
        try:
            event_index = int(index_str)
            self.timetable_service.delete_event(date_key, event_index)
            return AdminResponse.redirect(f"/timetables/{date_key}?msg=" + quote("Мероприятие удалено"))
        except Exception as e:
            return AdminResponse.redirect(f"/timetables/{date_key}?error=" + quote(str(e)))

    def _handle_post_day_event_toggle_children(self, request: AdminRequest, date_key: str) -> AdminResponse:
        index_str = request.form_data.get("event_index", "0")
        try:
            event_index = int(index_str)
            raw_children = request.form_data.get("is_children_activity")
            if raw_children is not None:
                is_children = str(raw_children).strip().lower() in ("1", "true", "yes", "on")
                self.timetable_service.set_event_children_activity(date_key, event_index, is_children)
            else:
                self.timetable_service.toggle_event_children_activity(date_key, event_index)
            return AdminResponse.redirect(f"/timetables/{date_key}")
        except Exception as e:
            return AdminResponse.redirect(f"/timetables/{date_key}?error=" + quote(str(e)))

    # --- Map Handlers ---

    def _handle_get_map(self, request: AdminRequest) -> AdminResponse:
        error = request.query_params.get("error")
        message = request.query_params.get("msg")
        maps = self.map_service.list_maps()
        html = AdminTemplateRenderer.render_map(
            map_versions=maps,
            error=error,
            message=message,
            has_unsaved_changes=self.has_unsaved_changes(),
        )
        return AdminResponse.html(html)

    def _handle_post_map_upload(self, request: AdminRequest) -> AdminResponse:
        set_active = str(request.form_data.get("set_active", "1")).strip() in ("1", "true", "True", "on", "yes")
        file_obj = request.files.get("map_file") or request.files.get("file")
        if not file_obj:
            return AdminResponse.redirect("/map?error=" + quote("Файл для загрузки не найден"))

        filename = file_obj.get("filename", "")
        content = file_obj.get("content", b"")
        if not filename or not content:
            return AdminResponse.redirect("/map?error=" + quote("Файл не может быть пустым"))

        try:
            saved_name = self.map_service.upload_map(
                filename=filename,
                content=content,
                set_as_active=set_active,
            )
            msg = f"Карта «{saved_name}» успешно загружена" + (" и выбрана активной!" if set_active else "!")
            return AdminResponse.redirect("/map?msg=" + quote(msg))
        except Exception as e:
            return AdminResponse.redirect("/map?error=" + quote(str(e)))

    def _handle_post_map_select(self, request: AdminRequest) -> AdminResponse:
        filename = request.form_data.get("filename", "").strip()
        if not filename:
            return AdminResponse.redirect("/map?error=" + quote("Имя файла карты не указано"))
        try:
            self.map_service.select_map(filename)
            return AdminResponse.redirect("/map?msg=" + quote(f"Карта «{filename}» выбрана как активная"))
        except Exception as e:
            return AdminResponse.redirect("/map?error=" + quote(str(e)))

    def _handle_post_map_delete(self, request: AdminRequest) -> AdminResponse:
        filename = request.form_data.get("filename", "").strip()
        if not filename:
            return AdminResponse.redirect("/map?error=" + quote("Имя файла карты не указано"))
        try:
            self.map_service.delete_map(filename)
            return AdminResponse.redirect("/map?msg=" + quote(f"Версия карты «{filename}» удалена"))
        except Exception as e:
            return AdminResponse.redirect("/map?error=" + quote(str(e)))

    def _handle_get_map_file(self, request: AdminRequest, filename: str) -> AdminResponse:
        res = self.map_service.get_map_file_content(filename)
        if not res:
            return AdminResponse.html("<h1>404 Map File Not Found</h1>", status_code=404)
        content_bytes, mime_type = res
        return AdminResponse.binary(content_bytes, content_type=mime_type)

    # --- API Dispatcher ---

    def _route_api(self, request: AdminRequest, path: str) -> AdminResponse:
        if path == "/api/save" and request.method == "POST":
            self.recs_service.save_to_disk()
            self.timetable_service.save_to_disk()
            self.map_service.save_to_disk()
            return AdminResponse.json({"status": "ok"})

        if path == "/api/discard" and request.method == "POST":
            self.recs_service.discard_changes()
            self.timetable_service.discard_changes()
            self.map_service.discard_changes()
            return AdminResponse.json({"status": "ok"})

        if path == "/api/map":
            if request.method == "GET":
                return AdminResponse.json({
                    "active_map": self.map_service.get_active_map(),
                    "maps": self.map_service.list_maps(),
                })
            if request.method == "POST":
                file_obj = request.files.get("map_file") or request.files.get("file")
                if file_obj:
                    set_active = str(request.form_data.get("set_active", "1")).strip() in ("1", "true", "True", "on", "yes")
                    saved_name = self.map_service.upload_map(
                        filename=file_obj.get("filename", ""),
                        content=file_obj.get("content", b""),
                        set_as_active=set_active,
                    )
                    return AdminResponse.json({"status": "ok", "filename": saved_name, "is_active": set_active})
                data = request.json() or {}
                if "content_base64" in data and "filename" in data:
                    import base64
                    content = base64.b64decode(data["content_base64"])
                    set_active = bool(data.get("set_active", True))
                    saved_name = self.map_service.upload_map(
                        filename=data["filename"],
                        content=content,
                        set_as_active=set_active,
                    )
                    return AdminResponse.json({"status": "ok", "filename": saved_name, "is_active": set_active})
                return AdminResponse.json({"error": "No file provided"}, status_code=400)

        if path == "/api/map/select" and request.method == "POST":
            data = request.json() or request.form_data or {}
            filename = data.get("filename", "")
            if not filename:
                return AdminResponse.json({"error": "filename required"}, status_code=400)
            try:
                self.map_service.select_map(filename)
                return AdminResponse.json({"status": "ok", "active_map": filename})
            except Exception as e:
                return AdminResponse.json({"error": str(e)}, status_code=400)

        if path == "/api/recs":
            if request.method == "GET":
                return AdminResponse.json(self.recs_service.load_data())
            if request.method == "POST":
                data = request.json() or {}
                self.recs_service.save_data(data)
                return AdminResponse.json({"status": "ok"})

        if path == "/api/locations" and request.method == "GET":
            return AdminResponse.json(self.timetable_service.get_all_locations())

        if path == "/api/timetables":
            if request.method == "GET":
                return AdminResponse.json(self.timetable_service.list_days())
            if request.method == "POST":
                payload = request.json() or {}
                date = payload.get("date", "")
                self.timetable_service.create_day(date)
                return AdminResponse.json({"status": "ok", "date": date}, status_code=201)

        if path.startswith("/api/timetables/"):
            date_key = path[len("/api/timetables/"):].split("/")[0]
            if request.method == "GET":
                data = self.timetable_service.get_day_dict(date_key)
                return AdminResponse.json(data)
            if request.method == "POST" and path.endswith("/events"):
                payload = request.json() or {}
                self.timetable_service.add_event(
                    date=date_key,
                    time=payload.get("time", ""),
                    title=payload.get("title", ""),
                    location=payload.get("location", ""),
                    description=payload.get("description", ""),
                    participants=payload.get("participants", []),
                    organizer=payload.get("organizer", ""),
                    is_children_activity=payload.get("is_children_activity", False),
                )
                return AdminResponse.json({"status": "ok"}, status_code=201)

        return AdminResponse.json({"error": "Endpoint not found"}, status_code=404)
