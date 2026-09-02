"""Service for loading and querying timetable data from JSON asset files."""

from datetime import datetime
import os
from typing import Dict, List, Optional

from bot.content import TIMETABLES_PATH
from bot.timetable.day import DayTimetable
from bot.timetable.event import Event


class TimetableService:
    """Service managing timetable data loading, retrieval, and formatting."""

    def __init__(self, timetables_dir: Optional[str] = None):
        self.timetables_dir = timetables_dir or TIMETABLES_PATH

    def _get_sort_key(self, date_str: str):
        for fmt in ("%d%m%Y", "%Y-%m-%d", "%d.%m.%Y"):
            try:
                dt = datetime.strptime(date_str, fmt)
                return (0, dt)
            except Exception:
                continue
        return (1, date_str)

    def get_available_dates(self, children_only: bool = False) -> List[str]:
        """Return list of all dates available in the timetables directory, sorted chronologically."""
        if not os.path.exists(self.timetables_dir):
            return []

        dates = []
        for filename in os.listdir(self.timetables_dir):
            if filename.endswith(".json"):
                date_part = filename[:-5]
                if children_only:
                    day = self.get_day(date_part)
                    if day and any(e.is_children_activity for e in day.events):
                        dates.append(date_part)
                else:
                    dates.append(date_part)

        return sorted(dates, key=self._get_sort_key)

    def get_day(self, date_str: str) -> Optional[DayTimetable]:
        """Load and return the DayTimetable for the given date string."""
        clean_date = date_str.strip()
        file_path = os.path.join(self.timetables_dir, f"{clean_date}.json")
        if not os.path.exists(file_path):
            return None

        try:
            return DayTimetable.from_file(file_path)
        except Exception:
            return None

    def get_locations(self, date_str: str, children_only: bool = False) -> List[str]:
        """Return list of distinct locations for the given date."""
        day = self.get_day(date_str)
        if not day:
            return []
        return day.get_locations(children_only=children_only)

    def get_events(self, date_str: str, location: str, children_only: bool = False) -> List[Event]:
        """Return list of events for the given date and location."""
        day = self.get_day(date_str)
        if not day:
            return []
        return day.get_events_for_location(location, children_only=children_only)

    def format_date_label(self, date_str: str) -> str:
        """Format raw date (DDMMYYYY) as DD.MM.YYYY."""
        day = self.get_day(date_str)
        if day:
            return day.format_date_display()
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:2]}.{date_str[2:4]}.{date_str[4:]}"
        return date_str

    def format_timetable(self, date_str: str, location: str, children_only: bool = False) -> str:
        """Format full schedule for the given date and location as informative Markdown."""
        date_label = self.format_date_label(date_str)
        events = self.get_events(date_str, location, children_only=children_only)

        header_title = "🎈 *Детская программа на " if children_only else "📅 *Расписание на "
        lines = [
            f"{header_title}{date_label}*",
            f"📍 *Площадка:* {location}\n",
        ]

        if not events:
            lines.append("На этой площадке событий не найдено.")
            return "\n".join(lines)

        for i, event in enumerate(events):
            lines.append(event.format_markdown())
            if i < len(events) - 1:
                lines.append("\n" + "─" * 22 + "\n")

        return "\n".join(lines)
