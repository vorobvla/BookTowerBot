"""HTML Template rendering for the admin web console."""

import html
import os
from typing import Any, Dict, List, Optional

from bot.participants.participant import Participant
from bot.recommendations.category import RecommendationCategory
from bot.timetable.day import DayTimetable

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


class AdminTemplateRenderer:
    """Renders HTML views and components for the admin interface using template files."""

    @classmethod
    def load_template(cls, filename: str) -> str:
        """Load template file content from the templates directory."""
        file_path = os.path.join(TEMPLATES_DIR, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    @classmethod
    def _render_layout(
        cls,
        title: str,
        content: str,
        active_tab: str = "",
        has_unsaved_changes: bool = False,
        return_to_path: Optional[str] = None,
    ) -> str:
        """Render base layout with navbar, alerts, container, and unsaved changes notice."""
        template = cls.load_template("layout.html")
        timetables_active = "active" if active_tab == "timetables" else ""
        locations_active = "active" if active_tab == "locations" else ""
        recs_active = "active" if active_tab == "recs" else ""
        map_active = "active" if active_tab == "map" else ""
        participants_active = "active" if active_tab == "participants" else ""
        broadcast_active = "active" if active_tab == "broadcast" else ""
        analytics_active = "active" if active_tab == "analytics" else ""
        data_active = "active" if active_tab == "data" else ""

        if return_to_path is None:
            if active_tab == "map":
                return_to_path = "/map"
            elif active_tab == "recs":
                return_to_path = "/recs"
            elif active_tab == "participants":
                return_to_path = "/participants"
            elif active_tab == "broadcast":
                return_to_path = "/broadcast"
            elif active_tab == "locations":
                return_to_path = "/locations"
            elif active_tab == "analytics":
                return_to_path = "/analytics"
            elif active_tab == "data":
                return_to_path = "/data"
            else:
                return_to_path = "/timetables"

        if has_unsaved_changes:
            banner_html = f"""
            <div class="alert" style="background-color: #fffbeb; border: 1px solid #fde68a; border-left: 5px solid #f59e0b; color: #92400e; padding: 1rem 1.25rem; margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; gap: 1rem; border-radius: 8px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 1.4rem;">⚠️</span>
                    <div>
                        <div style="font-weight: 700; font-size: 0.95rem; margin-bottom: 2px;">Есть несохраненные изменения!</div>
                        <div style="font-size: 0.875rem; color: #b45309;">Внесенные изменения не будут отображаться в боте, пока вы не сохраните их («Сохранить изменения и обновить бота»).</div>
                    </div>
                </div>
                <div style="display: flex; gap: 8px; flex-shrink: 0;">
                    <form method="POST" action="/save-changes" style="margin: 0;" onsubmit="return confirm('Сохранить все изменения и обновить информацию бота?');">
                        <input type="hidden" name="return_to" value="{html.escape(return_to_path)}">
                        <button type="submit" class="btn" style="background-color: #f59e0b; color: #ffffff; font-weight: 600; padding: 0.45rem 0.9rem; font-size: 0.85rem;">
                            Сохранить изменения и обновить бота
                        </button>
                    </form>
                </div>
            </div>
            """
            bar_notice_html = '<span style="color: #b45309; font-size: 0.85rem; font-weight: 500; margin-left: auto;">⚠️ Есть несохраненные данные: они не видны в боте до сохранения</span>'
        else:
            banner_html = ""
            bar_notice_html = ""

        return (
            template.replace("{{ title }}", html.escape(title))
            .replace("{{ timetables_active }}", timetables_active)
            .replace("{{ locations_active }}", locations_active)
            .replace("{{ recs_active }}", recs_active)
            .replace("{{ map_active }}", map_active)
            .replace("{{ participants_active }}", participants_active)
            .replace("{{ broadcast_active }}", broadcast_active)
            .replace("{{ analytics_active }}", analytics_active)
            .replace("{{ data_active }}", data_active)
            .replace("{{ return_to_path }}", html.escape(return_to_path))
            .replace("{{ unsaved_changes_banner }}", banner_html)
            .replace("{{ unsaved_changes_bar_notice }}", bar_notice_html)
            .replace("{{ content }}", content)
        )

    @classmethod
    def render_login(cls, error: Optional[str] = None, message: Optional[str] = None) -> str:
        """Render user authentication login page."""
        template = cls.load_template("login.html")
        alert_html = ""
        alert_tpl = cls.load_template("alert.html")
        if error:
            alert_html = (
                alert_tpl.replace("{{ alert_type }}", "alert-error")
                .replace("{{ message }}", html.escape(error))
            )
        elif message:
            alert_html = (
                alert_tpl.replace("{{ alert_type }}", "alert-success")
                .replace("{{ message }}", html.escape(message))
            )
        return template.replace("{{ error_html }}", alert_html)

    @classmethod
    def render_register(cls, error: Optional[str] = None, message: Optional[str] = None) -> str:
        """Render user registration page."""
        template = cls.load_template("register.html")
        alert_html = ""
        alert_tpl = cls.load_template("alert.html")
        if error:
            alert_html = (
                alert_tpl.replace("{{ alert_type }}", "alert-error")
                .replace("{{ message }}", html.escape(error))
            )
        elif message:
            alert_html = (
                alert_tpl.replace("{{ alert_type }}", "alert-success")
                .replace("{{ message }}", html.escape(message))
            )
        return template.replace("{{ error_html }}", alert_html)

    @classmethod
    def render_recs(
        cls,
        categories: List[RecommendationCategory],
        error: Optional[str] = None,
        message: Optional[str] = None,
        has_unsaved_changes: bool = False,
    ) -> str:
        """Render recommendations management page."""
        alert_tpl = cls.load_template("alert.html")
        alerts = []
        if error:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-error")
                .replace("{{ message }}", html.escape(error))
            )
        if message:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-success")
                .replace("{{ message }}", html.escape(message))
            )
        alerts_html = "".join(alerts)

        cat_card_tpl = cls.load_template("recs_category_card.html")
        book_row_tpl = cls.load_template("recs_book_row.html")
        empty_books_tpl = cls.load_template("recs_empty_books_row.html")
        empty_recs_tpl = cls.load_template("recs_empty.html")

        cat_cards = []
        for cat in categories:
            books_rows = []
            for idx, book in enumerate(cat.books):
                authors_str = ", ".join(book.authors) if book.authors else "—"
                sold_by_str = ", ".join(book.sold_by)
                desc_str = book.description or "—"

                row_html = (
                    book_row_tpl.replace("{{ title }}", html.escape(book.title))
                    .replace("{{ authors }}", html.escape(authors_str))
                    .replace("{{ sold_by }}", html.escape(sold_by_str))
                    .replace("{{ description }}", html.escape(desc_str))
                    .replace("{{ category_name }}", html.escape(cat.name))
                    .replace("{{ book_index }}", str(idx))
                )
                books_rows.append(row_html)

            books_content = "".join(books_rows) if books_rows else empty_books_tpl

            cat_emoji = cat.emoji if cat.emoji else "📚"
            cat_html = (
                cat_card_tpl.replace("{{ category_name }}", html.escape(cat.name))
                .replace("{{ category_emoji }}", html.escape(cat_emoji))
                .replace("{{ books_count }}", str(len(cat.books)))
                .replace("{{ books_rows }}", books_content)
            )
            cat_cards.append(cat_html)

        categories_html = "".join(cat_cards) if cat_cards else empty_recs_tpl

        recs_tpl = cls.load_template("recs.html")
        content = (
            recs_tpl.replace("{{ alerts_html }}", alerts_html)
            .replace("{{ categories_html }}", categories_html)
        )

        return cls._render_layout(
            title="Рекомендации",
            content=content,
            active_tab="recs",
            has_unsaved_changes=has_unsaved_changes,
        )

    @classmethod
    def render_timetables_list(
        cls,
        dates: List[str],
        master_classes: Optional[List[Dict[str, Any]]] = None,
        all_locations: Optional[List[str]] = None,
        error: Optional[str] = None,
        message: Optional[str] = None,
        has_unsaved_changes: bool = False,
    ) -> str:
        """Render list of timetable dates and master-classes panel."""
        alert_tpl = cls.load_template("alert.html")
        alerts = []
        if error:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-error")
                .replace("{{ message }}", html.escape(error))
            )
        if message:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-success")
                .replace("{{ message }}", html.escape(message))
            )
        alerts_html = "".join(alerts)

        date_row_tpl = cls.load_template("timetables_date_row.html")
        empty_row_tpl = cls.load_template("timetables_empty_row.html")

        rows = []
        for date_key in dates:
            display_date = date_key
            if len(date_key) == 8 and date_key.isdigit():
                display_date = f"{date_key[:2]}.{date_key[2:4]}.{date_key[4:]}"

            row_html = (
                date_row_tpl.replace("{{ display_date }}", html.escape(display_date))
                .replace("{{ date_key }}", html.escape(date_key))
            )
            rows.append(row_html)

        date_rows_content = "".join(rows) if rows else empty_row_tpl

        loc_option_tpl = cls.load_template("location_option.html")
        loc_options = []
        if all_locations:
            for loc in all_locations:
                loc_options.append(
                    loc_option_tpl.replace("{{ value }}", html.escape(loc))
                    .replace("{{ label }}", html.escape(loc))
                )
        loc_options_html = "".join(loc_options)

        mc_rows = []
        if master_classes:
            mc_row_tpl = cls.load_template("timetables_master_class_row.html")
            for item in master_classes:
                date_key = str(item.get("date_key", "")).strip()
                display_date = date_key
                if len(date_key) == 8 and date_key.isdigit():
                    display_date = f"{date_key[:2]}.{date_key[2:4]}.{date_key[4:]}"

                participants_raw = item.get("participants", [])
                if isinstance(participants_raw, list):
                    participants_str = ", ".join(participants_raw) if participants_raw else ""
                else:
                    participants_str = str(participants_raw) if participants_raw else ""
                display_participants = participants_str if participants_str else "—"
                raw_organizer = item.get("organizer", "") or ""
                display_organizer = raw_organizer if raw_organizer else "—"
                raw_title = str(item.get("title", ""))
                raw_location = str(item.get("location", ""))
                raw_time = str(item.get("time", ""))
                raw_description = item.get("description", "") or ""
                if raw_description:
                    if len(raw_description) > 200:
                        display_desc_text = raw_description[:200] + "..."
                    else:
                        display_desc_text = raw_description
                    display_description = (
                        f'<span class="event-desc-hover" '
                        f'data-title="{html.escape(raw_title, quote=True)}" '
                        f'data-description="{html.escape(raw_description, quote=True)}" '
                        f'onmouseenter="showEventDescriptionToast(this, event)" '
                        f'onmousemove="moveEventDescriptionToast(event)" '
                        f'onmouseleave="hideEventDescriptionToast()">'
                        f'{html.escape(display_desc_text)}</span>'
                    )
                else:
                    display_description = "—"

                is_children = bool(item.get("is_children_activity", False))
                checked_attr = "checked" if is_children else ""
                is_children_num = "1" if is_children else "0"

                is_master = bool(item.get("is_master_class", False))
                master_checked_attr = "checked" if is_master else ""
                is_master_class_num = "1" if is_master else "0"

                row_html = (
                    mc_row_tpl.replace("{{ date_key }}", html.escape(date_key))
                    .replace("{{ display_date }}", html.escape(display_date))
                    .replace("{{ event_index }}", str(item.get("event_index", 0)))
                    .replace("{{ time }}", html.escape(raw_time))
                    .replace("{{ title }}", html.escape(raw_title))
                    .replace("{{ location }}", html.escape(raw_location))
                    .replace("{{ organizer }}", html.escape(str(display_organizer)))
                    .replace("{{ participants }}", html.escape(str(display_participants)))
                    .replace("{{ description }}", display_description)
                    .replace("{{ checked_attr }}", checked_attr)
                    .replace("{{ is_children_activity_num }}", is_children_num)
                    .replace("{{ master_checked_attr }}", master_checked_attr)
                    .replace("{{ is_master_class_num }}", is_master_class_num)
                    .replace("{{ title_attr }}", html.escape(raw_title, quote=True))
                    .replace("{{ location_attr }}", html.escape(raw_location, quote=True))
                    .replace("{{ organizer_attr }}", html.escape(raw_organizer, quote=True))
                    .replace("{{ participants_attr }}", html.escape(participants_str, quote=True))
                    .replace("{{ description_attr }}", html.escape(raw_description, quote=True))
                )
                mc_rows.append(row_html)

        empty_mc_tpl = cls.load_template("timetables_empty_master_classes_row.html")
        master_class_rows_content = "".join(mc_rows) if mc_rows else empty_mc_tpl
        master_classes_count = str(len(mc_rows))

        timetables_tpl = cls.load_template("timetables_list.html")
        content = (
            timetables_tpl.replace("{{ alerts_html }}", alerts_html)
            .replace("{{ date_rows }}", date_rows_content)
            .replace("{{ master_class_rows }}", master_class_rows_content)
            .replace("{{ master_classes_count }}", master_classes_count)
            .replace("{{ location_options }}", loc_options_html)
        )

        return cls._render_layout(
            title="Расписания",
            content=content,
            active_tab="timetables",
            has_unsaved_changes=has_unsaved_changes,
            return_to_path="/timetables",
        )

    @classmethod
    def render_locations(
        cls,
        locations_summary: List[Dict[str, Any]],
        error: Optional[str] = None,
        message: Optional[str] = None,
        has_unsaved_changes: bool = False,
    ) -> str:
        """Render locations management view with summary of event counts and rename capabilities."""
        alert_tpl = cls.load_template("alert.html")
        alerts = []
        if error:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-error")
                .replace("{{ message }}", html.escape(error))
            )
        if message:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-success")
                .replace("{{ message }}", html.escape(message))
            )
        alerts_html = "".join(alerts)

        if not locations_summary:
            location_rows = cls.load_template("locations_empty_row.html")
        else:
            row_tpl = cls.load_template("locations_row.html")
            rows = []
            for item in locations_summary:
                loc_name = item.get("name", "")
                events_count = item.get("events_count", 0)
                raw_days = item.get("days", [])

                formatted_days = []
                for d in raw_days:
                    if len(d) == 8 and d.isdigit():
                        formatted_days.append(f"{d[:2]}.{d[2:4]}.{d[4:]}")
                    else:
                        formatted_days.append(d)
                days_display = ", ".join(formatted_days) if formatted_days else "—"

                row_rendered = (
                    row_tpl.replace("{{ location_name }}", html.escape(loc_name))
                    .replace("{{ location_raw }}", html.escape(loc_name, quote=True))
                    .replace("{{ events_count }}", str(events_count))
                    .replace("{{ days_display }}", html.escape(days_display))
                )
                rows.append(row_rendered)
            location_rows = "".join(rows)

        locations_tpl = cls.load_template("locations.html")
        content = (
            locations_tpl.replace("{{ alerts_html }}", alerts_html)
            .replace("{{ locations_count }}", str(len(locations_summary)))
            .replace("{{ location_rows }}", location_rows)
        )

        return cls._render_layout(
            title="Управление локациями",
            content=content,
            active_tab="locations",
            has_unsaved_changes=has_unsaved_changes,
        )

    @classmethod
    def render_day_timetable(
        cls,
        date_key: str,
        timetable: DayTimetable,
        all_locations: List[str],
        error: Optional[str] = None,
        message: Optional[str] = None,
        has_unsaved_changes: bool = False,
    ) -> str:
        """Render single day timetable events management with location dropdown & create-new capability."""
        alert_tpl = cls.load_template("alert.html")
        alerts = []
        if error:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-error")
                .replace("{{ message }}", html.escape(error))
            )
        if message:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-success")
                .replace("{{ message }}", html.escape(message))
            )
        alerts_html = "".join(alerts)

        display_date = timetable.format_date_display() if hasattr(timetable, "format_date_display") else date_key

        loc_option_tpl = cls.load_template("location_option.html")
        loc_options = []
        for loc in all_locations:
            loc_options.append(
                loc_option_tpl.replace("{{ value }}", html.escape(loc))
                .replace("{{ label }}", html.escape(loc))
            )
        loc_options_html = "".join(loc_options)

        event_row_tpl = cls.load_template("day_event_row.html")
        empty_events_tpl = cls.load_template("day_empty_events_row.html")

        all_event_rows = []
        general_event_rows = []
        children_event_rows = []

        for idx, event in enumerate(timetable.events):
            participants_str = ", ".join(event.participants) if event.participants else ""
            display_participants = participants_str if participants_str else "—"
            display_organizer = event.organizer if event.organizer else "—"
            raw_description = event.description if event.description else ""
            if raw_description:
                if len(raw_description) > 200:
                    display_desc_text = raw_description[:200] + "..."
                else:
                    display_desc_text = raw_description
                display_description = (
                    f'<span class="event-desc-hover" '
                    f'data-title="{html.escape(event.title, quote=True)}" '
                    f'data-description="{html.escape(raw_description, quote=True)}" '
                    f'onmouseenter="showEventDescriptionToast(this, event)" '
                    f'onmousemove="moveEventDescriptionToast(event)" '
                    f'onmouseleave="hideEventDescriptionToast()">'
                    f'{html.escape(display_desc_text)}</span>'
                )
            else:
                display_description = "—"

            checked_attr = "checked" if event.is_children_activity else ""
            is_children_num = "1" if event.is_children_activity else "0"

            master_checked_attr = "checked" if getattr(event, "is_master_class", False) else ""
            is_master_class_num = "1" if getattr(event, "is_master_class", False) else "0"

            row_html = (
                event_row_tpl.replace("{{ time }}", html.escape(event.time))
                .replace("{{ title }}", html.escape(event.title))
                .replace("{{ location }}", html.escape(event.location))
                .replace("{{ organizer }}", html.escape(display_organizer))
                .replace("{{ participants }}", html.escape(display_participants))
                .replace("{{ description }}", display_description)
                .replace("{{ date_key }}", html.escape(date_key))
                .replace("{{ event_index }}", str(idx))
                .replace("{{ checked_attr }}", checked_attr)
                .replace("{{ is_children_activity_num }}", is_children_num)
                .replace("{{ master_checked_attr }}", master_checked_attr)
                .replace("{{ is_master_class_num }}", is_master_class_num)
                .replace("{{ title_attr }}", html.escape(event.title, quote=True))
                .replace("{{ location_attr }}", html.escape(event.location, quote=True))
                .replace("{{ organizer_attr }}", html.escape(event.organizer or "", quote=True))
                .replace("{{ participants_attr }}", html.escape(participants_str, quote=True))
                .replace("{{ description_attr }}", html.escape(raw_description, quote=True))
            )
            all_event_rows.append(row_html)
            if event.is_children_activity:
                children_event_rows.append(row_html)
            else:
                general_event_rows.append(row_html)

        empty_general = '<tr><td colspan="9" style="text-align:center; color:#94a3b8;">Нет запланированных событий основной программы</td></tr>'
        empty_children = '<tr><td colspan="9" style="text-align:center; color:#94a3b8;">Нет запланированных событий детской программы</td></tr>'

        event_rows_content = "".join(all_event_rows) if all_event_rows else empty_events_tpl
        general_rows_content = "".join(general_event_rows) if general_event_rows else empty_general
        children_rows_content = "".join(children_event_rows) if children_event_rows else empty_children

        day_tpl = cls.load_template("day_timetable.html")
        content = (
            day_tpl.replace("{{ alerts_html }}", alerts_html)
            .replace("{{ display_date }}", html.escape(display_date))
            .replace("{{ date_key }}", html.escape(date_key))
            .replace("{{ events_count }}", str(len(timetable.events)))
            .replace("{{ general_events_count }}", str(len(general_event_rows)))
            .replace("{{ children_events_count }}", str(len(children_event_rows)))
            .replace("{{ event_rows }}", event_rows_content)
            .replace("{{ general_event_rows }}", general_rows_content)
            .replace("{{ children_event_rows }}", children_rows_content)
            .replace("{{ location_options }}", loc_options_html)
        )

        return cls._render_layout(
            title=f"Расписание {display_date}",
            content=content,
            active_tab="timetables",
            has_unsaved_changes=has_unsaved_changes,
            return_to_path=f"/timetables/{date_key}",
        )

    @classmethod
    def render_map(
        cls,
        map_versions: List[Dict[str, Any]],
        error: Optional[str] = None,
        message: Optional[str] = None,
        has_unsaved_changes: bool = False,
    ) -> str:
        """Render venue map management page."""
        alert_tpl = cls.load_template("alert.html")
        alerts = []
        if error:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-error")
                .replace("{{ message }}", html.escape(error))
            )
        if message:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-success")
                .replace("{{ message }}", html.escape(message))
            )
        alerts_html = "".join(alerts)

        active_version = next((m for m in map_versions if m.get("is_active")), None)
        if active_version:
            active_filename = active_version["filename"]
            active_preview_url = active_version["preview_url"]
            active_size = active_version["formatted_size"]
            active_date = active_version["modified_at"]
            active_map_content = f"""
            <div style="text-align: center; margin-bottom: 1rem;">
                <a href="{active_preview_url}" target="_blank">
                    <img src="{active_preview_url}" alt="{html.escape(active_filename)}" style="max-width: 100%; max-height: 240px; border-radius: 6px; border: 1px solid var(--border); box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                </a>
            </div>
            <div style="font-size: 0.9rem; background: #f8fafc; padding: 0.75rem; border-radius: 6px; border: 1px solid var(--border);">
                <div><strong>Файл:</strong> {html.escape(active_filename)}</div>
                <div><strong>Размер:</strong> {html.escape(active_size)}</div>
                <div><strong>Обновлен:</strong> {html.escape(active_date)}</div>
            </div>
            """
        else:
            active_map_content = """
            <div style="padding: 2rem; text-align: center; color: var(--text-muted); background: #f8fafc; border-radius: 6px; border: 1px dashed var(--border);">
                Активная карта еще не установлена. Загрузите файл карты справа.
            </div>
            """

        row_tpl = cls.load_template("map_version_row.html")
        empty_tpl = cls.load_template("map_empty.html")

        if not map_versions:
            map_rows = empty_tpl
        else:
            rows = []
            for item in map_versions:
                fname = item["filename"]
                is_active = item["is_active"]
                preview_url = item["preview_url"]
                formatted_size = item["formatted_size"]
                modified_at = item["modified_at"]

                row_style = "background-color: #f0fdf4;" if is_active else ""
                if is_active:
                    status_badge = '<span style="background: #10b981; color: #ffffff; font-size: 0.8rem; font-weight: 600; padding: 3px 10px; border-radius: 9999px;">Активная</span>'
                    action_buttons = ""
                else:
                    status_badge = '<span style="color: var(--text-muted); font-size: 0.85rem;">Архивная</span>'
                    action_buttons = f"""
                    <form method="POST" action="/map/select" style="margin: 0; display: inline;">
                        <input type="hidden" name="filename" value="{html.escape(fname)}">
                        <button type="submit" class="btn btn-sm" style="background-color: var(--primary);">Выбрать</button>
                    </form>
                    <form method="POST" action="/map/delete" style="margin: 0; display: inline;" onsubmit="return confirm('Удалить эту версию карты?');">
                        <input type="hidden" name="filename" value="{html.escape(fname)}">
                        <button type="submit" class="btn btn-sm btn-danger">Удалить</button>
                    </form>
                    """

                row_rendered = (
                    row_tpl.replace("{{ row_style }}", row_style)
                    .replace("{{ preview_url }}", preview_url)
                    .replace("{{ filename }}", html.escape(fname))
                    .replace("{{ formatted_size }}", html.escape(formatted_size))
                    .replace("{{ modified_at }}", html.escape(modified_at))
                    .replace("{{ status_badge }}", status_badge)
                    .replace("{{ action_buttons }}", action_buttons)
                )
                rows.append(row_rendered)
            map_rows = "".join(rows)

        upload_btn = f"""
        <div style="display: flex; gap: 8px; flex-shrink: 0;">
            <form method="POST" action="/save-changes" style="margin: 0;" onsubmit="return confirm('Сохранить все изменения и обновить информацию бота?');">
                <button type="submit" class="btn" style="background-color: #f59e0b; color: #ffffff; font-weight: 600; padding: 0.45rem 0.9rem; font-size: 0.85rem;">
                    Сохранить и обновить бота
                </button>
            </form>
        </div>
        """ if has_unsaved_changes else ""

        map_tpl = cls.load_template("map.html")
        content = (
            map_tpl.replace("{{ alerts_html }}", alerts_html)
            .replace("{{ active_map_content }}", active_map_content)
            .replace("{{ map_rows }}", map_rows)
            .replace("{{ unsaved_changes_banner }}", upload_btn)
        )

        return cls._render_layout(
            title="Управление картой ярмарки",
            content=content,
            active_tab="map",
            has_unsaved_changes=has_unsaved_changes,
        )

    @classmethod
    def render_participants(
        cls,
        participants: List[Participant],
        has_unsaved_changes: bool = False,
        error_msg: Optional[str] = None,
        success_msg: Optional[str] = None,
    ) -> str:
        """Render participants management view with participant list, add card, and edit modal."""
        alert_tpl = cls.load_template("alert.html")
        alerts = []
        if error_msg:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-error")
                .replace("{{ message }}", html.escape(error_msg))
            )
        if success_msg:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-success")
                .replace("{{ message }}", html.escape(success_msg))
            )
        alerts_html = "".join(alerts)

        if not participants:
            participants_rows = cls.load_template("participants_empty_row.html")
        else:
            row_tpl = cls.load_template("participants_row.html")
            rows = []
            for idx, p in enumerate(participants):
                link_href = p.link
                if link_href and not link_href.startswith(("http://", "https://")):
                    link_href = f"https://{link_href}"
                link_html = (
                    f'<a href="{html.escape(link_href)}" target="_blank" rel="noopener noreferrer" style="color: var(--primary); text-decoration: none;">🔗 {html.escape(p.link)}</a>'
                    if p.link
                    else '<span style="color: var(--text-muted); font-size: 0.85rem;">—</span>'
                )
                row_rendered = (
                    row_tpl.replace("{{ participant_index }}", str(idx))
                    .replace("{{ stand }}", html.escape(p.stand))
                    .replace("{{ stand_raw }}", html.escape(p.stand, quote=True))
                    .replace("{{ name }}", html.escape(p.name))
                    .replace("{{ name_raw }}", html.escape(p.name, quote=True))
                    .replace("{{ link_html }}", link_html)
                    .replace("{{ link_raw }}", html.escape(p.link, quote=True))
                    .replace("{{ description }}", html.escape(p.description) if p.description else '<span style="color: var(--text-muted); font-size: 0.85rem;">—</span>')
                    .replace("{{ description_raw }}", html.escape(p.description, quote=True))
                )
                rows.append(row_rendered)
            participants_rows = "".join(rows)

        part_tpl = cls.load_template("participants.html")
        content = (
            part_tpl.replace("{{ alerts_html }}", alerts_html)
            .replace("{{ participants_count }}", str(len(participants)))
            .replace("{{ participants_rows }}", participants_rows)
        )

        return cls._render_layout(
            title="Управление участниками и стендами",
            content=content,
            active_tab="participants",
            has_unsaved_changes=has_unsaved_changes,
        )

    @classmethod
    def render_data_page(
        cls,
        error: Optional[str] = None,
        message: Optional[str] = None,
        has_unsaved_changes: bool = False,
    ) -> str:
        """Render data import and export page."""
        template = cls.load_template("data.html")
        alerts = []
        alert_tpl = cls.load_template("alert.html")
        if error:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-error")
                .replace("{{ message }}", html.escape(error))
            )
        if message:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-success")
                .replace("{{ message }}", html.escape(message))
            )
        alerts_html = "".join(alerts)

        content = template.replace("{{ alerts_html }}", alerts_html)
        return cls._render_layout(
            title="Импорт и экспорт данных",
            content=content,
            active_tab="data",
            has_unsaved_changes=has_unsaved_changes,
            return_to_path="/data",
        )

    @classmethod
    def render_analytics(
        cls,
        summary: Dict[str, Any],
        error: Optional[str] = None,
        message: Optional[str] = None,
        has_unsaved_changes: bool = False,
    ) -> str:
        """Render UX analytics and metrics page."""
        template = cls.load_template("analytics.html")
        alerts = []
        alert_tpl = cls.load_template("alert.html")
        if error:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-error")
                .replace("{{ message }}", html.escape(error))
            )
        if message:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-success")
                .replace("{{ message }}", html.escape(message))
            )
        alerts_html = "".join(alerts)

        events = summary.get("events", {})
        users = summary.get("users", {})
        paths = summary.get("paths", [])
        wishlist = summary.get("wishlist", [])
        menu_buttons = summary.get("menu_buttons", [])
        text_commands = summary.get("text_commands", [])

        # Format menu buttons rows
        if not menu_buttons:
            menu_buttons_rows = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Нет данных о нажатиях кнопок меню</td></tr>'
        else:
            mb_rows = []
            for idx, mb in enumerate(menu_buttons, 1):
                mb_rows.append(
                    f'<tr>'
                    f'<td style="text-align: center; color: var(--text-muted);">{idx}</td>'
                    f'<td><strong>{html.escape(mb["button"])}</strong></td>'
                    f'<td><code style="font-size: 0.85rem; background: #f3f4f6; padding: 2px 6px; border-radius: 4px;">{html.escape(mb.get("callback", ""))}</code></td>'
                    f'<td style="text-align: center;"><span class="badge" style="background: #e0f2fe; color: #0369a1; font-weight: 600;">{mb["count"]}</span></td>'
                    f'</tr>'
                )
            menu_buttons_rows = "".join(mb_rows)

        # Format text commands rows
        if not text_commands:
            text_commands_rows = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Нет данных об использовании команд</td></tr>'
        else:
            tc_rows = []
            for idx, tc in enumerate(text_commands, 1):
                tc_rows.append(
                    f'<tr>'
                    f'<td style="text-align: center; color: var(--text-muted);">{idx}</td>'
                    f'<td><code style="font-family: monospace; background: #ede9fe; color: #5b21b6; padding: 3px 8px; border-radius: 4px; font-weight: 600;">{html.escape(tc["command"])}</code></td>'
                    f'<td>{html.escape(tc.get("description", ""))}</td>'
                    f'<td style="text-align: center;"><span class="badge" style="background: #f5f3ff; color: #6d28d9; font-weight: 600;">{tc["count"]}</span></td>'
                    f'</tr>'
                )
            text_commands_rows = "".join(tc_rows)

        # Format paths rows
        if not paths:
            paths_rows = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Нет зафиксированных путей пользователей</td></tr>'
        else:
            p_rows = []
            for idx, p in enumerate(paths, 1):
                p_rows.append(
                    f'<tr>'
                    f'<td style="text-align: center; color: var(--text-muted);">{idx}</td>'
                    f'<td><span style="font-family: monospace; background: #eef2ff; color: #3730a3; padding: 4px 8px; border-radius: 4px; font-weight: 500; font-size: 0.9rem;">{html.escape(p["path"])}</span></td>'
                    f'<td style="text-align: center; font-weight: 600;">{p["count"]}</td>'
                    f'<td style="text-align: center;"><span class="badge" style="background: #e0e7ff; color: #3730a3; font-weight: 600;">{p["percentage"]}%</span></td>'
                    f'</tr>'
                )
            paths_rows = "".join(p_rows)

        # Format wishlist rows
        if not wishlist:
            wishlist_rows = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Пока нет добавленных книг в вишлисты</td></tr>'
        else:
            w_rows = []
            for idx, w in enumerate(wishlist, 1):
                isbn_val = html.escape(w.get("isbn") or "—")
                w_rows.append(
                    f'<tr>'
                    f'<td style="text-align: center; color: var(--text-muted);">{idx}</td>'
                    f'<td><strong>{html.escape(w["title"])}</strong></td>'
                    f'<td><code style="font-size: 0.85rem;">{isbn_val}</code></td>'
                    f'<td style="text-align: center;"><span class="badge" style="background: #ecfdf5; color: #047857; font-weight: 600;">{w["count"]}</span></td>'
                    f'</tr>'
                )
            wishlist_rows = "".join(w_rows)

        content = (
            template.replace("{{ alerts_html }}", alerts_html)
            .replace("{{ total_users }}", str(users.get("total_users", 0)))
            .replace("{{ total_chats }}", str(users.get("total_chats", 0)))
            .replace("{{ inline_keyboard_events }}", str(events.get("inline_keyboard_events", 0)))
            .replace("{{ commands_count }}", str(events.get("commands", 0)))
            .replace("{{ unrecognized_messages }}", str(events.get("unrecognized_messages", 0)))
            .replace("{{ total_events }}", str(events.get("total_events", 0)))
            .replace("{{ menu_buttons_count }}", str(len(menu_buttons)))
            .replace("{{ menu_buttons_rows }}", menu_buttons_rows)
            .replace("{{ text_commands_count }}", str(len(text_commands)))
            .replace("{{ text_commands_rows }}", text_commands_rows)
            .replace("{{ paths_count }}", str(len(paths)))
            .replace("{{ paths_rows }}", paths_rows)
            .replace("{{ wishlist_count }}", str(len(wishlist)))
            .replace("{{ wishlist_rows }}", wishlist_rows)
        )

        return cls._render_layout(
            title="UX Аналитика",
            content=content,
            active_tab="analytics",
            has_unsaved_changes=has_unsaved_changes,
            return_to_path="/analytics",
        )

    @classmethod
    def render_broadcast(
        cls,
        chat_count: int,
        commands: List[Dict[str, str]],
        is_bot_online: bool = True,
        error: Optional[str] = None,
        message: Optional[str] = None,
        has_unsaved_changes: bool = False,
    ) -> str:
        """Render broadcast management page with composer and confirmation modal."""
        template = cls.load_template("broadcast.html")
        alerts = []
        alert_tpl = cls.load_template("alert.html")
        if error:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-error")
                .replace("{{ message }}", html.escape(error))
            )
        if message:
            alerts.append(
                alert_tpl.replace("{{ alert_type }}", "alert-success")
                .replace("{{ message }}", html.escape(message))
            )
        alerts_html = "".join(alerts)

        if not is_bot_online:
            status_bg_color = "#fee2e2"
            status_text_color = "#991b1b"
            status_icon = "🔴"
            status_label = "(Бот офлайн / недоступен)"
        elif chat_count > 0:
            status_bg_color = "#dcfce7"
            status_text_color = "#15803d"
            status_icon = "🟢"
            status_label = "(Бот онлайн, готов к отправке)"
        else:
            status_bg_color = "#fef9c3"
            status_text_color = "#a16207"
            status_icon = "🟡"
            status_label = "(Бот онлайн, 0 активных чатов)"

        cmd_opts = []
        for cmd in commands:
            cmd_name = html.escape(cmd.get("command", ""))
            cmd_title = html.escape(cmd.get("title", cmd_name))
            cmd_desc = html.escape(cmd.get("description", ""))
            label = f"{cmd_title} — {cmd_desc}" if cmd_desc else cmd_title
            cmd_opts.append(f'<option value="{cmd_name}">{label}</option>')
        command_options_html = "\n".join(cmd_opts)

        content = (
            template.replace("{{ alert }}", alerts_html)
            .replace("{{ chat_count }}", str(chat_count))
            .replace("{{ status_bg_color }}", status_bg_color)
            .replace("{{ status_text_color }}", status_text_color)
            .replace("{{ status_icon }}", status_icon)
            .replace("{{ status_label }}", status_label)
            .replace("{{ command_options }}", command_options_html)
        )

        return cls._render_layout(
            title="Рассылка",
            content=content,
            active_tab="broadcast",
            has_unsaved_changes=has_unsaved_changes,
            return_to_path="/broadcast",
        )
