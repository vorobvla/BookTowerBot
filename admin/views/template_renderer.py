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
        recs_active = "active" if active_tab == "recs" else ""
        map_active = "active" if active_tab == "map" else ""
        participants_active = "active" if active_tab == "participants" else ""

        if return_to_path is None:
            if active_tab == "map":
                return_to_path = "/map"
            elif active_tab == "recs":
                return_to_path = "/recs"
            elif active_tab == "participants":
                return_to_path = "/participants"
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
            .replace("{{ recs_active }}", recs_active)
            .replace("{{ map_active }}", map_active)
            .replace("{{ participants_active }}", participants_active)
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
        error: Optional[str] = None,
        message: Optional[str] = None,
        has_unsaved_changes: bool = False,
    ) -> str:
        """Render list of timetable dates."""
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

        timetables_tpl = cls.load_template("timetables_list.html")
        content = (
            timetables_tpl.replace("{{ alerts_html }}", alerts_html)
            .replace("{{ date_rows }}", date_rows_content)
        )

        return cls._render_layout(
            title="Расписания",
            content=content,
            active_tab="timetables",
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
            display_description = event.description if event.description else "—"

            checked_attr = "checked" if event.is_children_activity else ""
            is_children_num = "1" if event.is_children_activity else "0"

            row_html = (
                event_row_tpl.replace("{{ time }}", html.escape(event.time))
                .replace("{{ title }}", html.escape(event.title))
                .replace("{{ location }}", html.escape(event.location))
                .replace("{{ organizer }}", html.escape(display_organizer))
                .replace("{{ participants }}", html.escape(display_participants))
                .replace("{{ description }}", html.escape(display_description))
                .replace("{{ date_key }}", html.escape(date_key))
                .replace("{{ event_index }}", str(idx))
                .replace("{{ checked_attr }}", checked_attr)
                .replace("{{ is_children_activity_num }}", is_children_num)
                .replace("{{ title_attr }}", html.escape(event.title, quote=True))
                .replace("{{ location_attr }}", html.escape(event.location, quote=True))
                .replace("{{ organizer_attr }}", html.escape(event.organizer or "", quote=True))
                .replace("{{ participants_attr }}", html.escape(participants_str, quote=True))
                .replace("{{ description_attr }}", html.escape(event.description or "", quote=True))
            )
            all_event_rows.append(row_html)
            if event.is_children_activity:
                children_event_rows.append(row_html)
            else:
                general_event_rows.append(row_html)

        empty_general = '<tr><td colspan="8" style="text-align:center; color:#94a3b8;">Нет запланированных событий основной программы</td></tr>'
        empty_children = '<tr><td colspan="8" style="text-align:center; color:#94a3b8;">Нет запланированных событий детской программы</td></tr>'

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
