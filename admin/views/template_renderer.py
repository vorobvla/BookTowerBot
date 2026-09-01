"""HTML Template rendering for the admin web console."""

import html
import os
from typing import Any, Dict, List, Optional

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
    def _render_layout(cls, title: str, content: str, active_tab: str = "") -> str:
        """Render base layout with navbar, alerts, and container."""
        template = cls.load_template("layout.html")
        timetables_active = "active" if active_tab == "timetables" else ""
        recs_active = "active" if active_tab == "recs" else ""
        return (
            template.replace("{{ title }}", html.escape(title))
            .replace("{{ timetables_active }}", timetables_active)
            .replace("{{ recs_active }}", recs_active)
            .replace("{{ content }}", content)
        )

    @classmethod
    def render_login(cls, error: Optional[str] = None) -> str:
        """Render user authentication login page."""
        template = cls.load_template("login.html")
        error_html = ""
        if error:
            alert_tpl = cls.load_template("alert.html")
            error_html = (
                alert_tpl.replace("{{ alert_type }}", "alert-error")
                .replace("{{ message }}", html.escape(error))
            )
        return template.replace("{{ error_html }}", error_html)

    @classmethod
    def render_recs(
        cls,
        categories: List[RecommendationCategory],
        error: Optional[str] = None,
        message: Optional[str] = None,
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

        return cls._render_layout(title="Рекомендации", content=content, active_tab="recs")

    @classmethod
    def render_timetables_list(
        cls,
        dates: List[str],
        error: Optional[str] = None,
        message: Optional[str] = None,
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

        return cls._render_layout(title="Расписания", content=content, active_tab="timetables")

    @classmethod
    def render_day_timetable(
        cls,
        date_key: str,
        timetable: DayTimetable,
        all_locations: List[str],
        error: Optional[str] = None,
        message: Optional[str] = None,
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

        event_rows = []
        for idx, event in enumerate(timetable.events):
            participants_str = ", ".join(event.participants) if event.participants else "—"
            row_html = (
                event_row_tpl.replace("{{ time }}", html.escape(event.time))
                .replace("{{ title }}", html.escape(event.title))
                .replace("{{ location }}", html.escape(event.location))
                .replace("{{ organizer }}", html.escape(event.organizer or "—"))
                .replace("{{ participants }}", html.escape(participants_str))
                .replace("{{ description }}", html.escape(event.description or "—"))
                .replace("{{ date_key }}", html.escape(date_key))
                .replace("{{ event_index }}", str(idx))
            )
            event_rows.append(row_html)

        event_rows_content = "".join(event_rows) if event_rows else empty_events_tpl

        day_tpl = cls.load_template("day_timetable.html")
        content = (
            day_tpl.replace("{{ alerts_html }}", alerts_html)
            .replace("{{ display_date }}", html.escape(display_date))
            .replace("{{ date_key }}", html.escape(date_key))
            .replace("{{ events_count }}", str(len(timetable.events)))
            .replace("{{ event_rows }}", event_rows_content)
            .replace("{{ location_options }}", loc_options_html)
        )

        return cls._render_layout(title=f"Расписание {display_date}", content=content, active_tab="timetables")
