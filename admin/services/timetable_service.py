"""Service for managing timetable dates and events in the admin console."""

import copy
from datetime import datetime
import json
import os
import re
from typing import Any, Dict, List, Optional

from bot.content import TIMETABLES_PATH
from bot.timetable.day import DayTimetable
from bot.timetable.event import Event


class AdminTimetableService:
    """Provides CRUD operations and validation for timetables and events."""

    TIME_PATTERN = re.compile(
        r"^([0-1]?[0-9]|2[0-3]):([0-5][0-9])(?:\s*-\s*([0-1]?[0-9]|2[0-3]):([0-5][0-9]))?$"
    )

    def __init__(self, directory_path: Optional[str] = None):
        self.directory_path = directory_path or TIMETABLES_PATH
        self._staged_days: Dict[str, Optional[Dict[str, Any]]] = {}
        self._has_pending_changes: bool = False

    @classmethod
    def validate_and_normalize_date(cls, date_str: str) -> str:
        """Validate date string and normalize it into DDMMYYYY format."""
        clean = (date_str or "").strip()
        if not clean:
            raise ValueError("Field 'date' is mandatory and cannot be empty / Поле 'Дата' обязательно")

        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d%m%Y", "%d/%m/%Y", "%Y.%m.%d"):
            try:
                dt = datetime.strptime(clean, fmt)
                return dt.strftime("%d%m%Y")
            except ValueError:
                continue

        raise ValueError(
            "Некорректный формат даты. Используйте формат ДД.ММ.ГГГГ или ГГГГ-ММ-ДД"
        )

    @classmethod
    def validate_time(cls, time_str: str) -> str:
        """Validate start time string (HH:MM)."""
        clean = (time_str or "").strip()
        if not clean:
            raise ValueError("Field 'time' is mandatory and cannot be empty / Поле 'Время' обязательно для заполнения")

        match = cls.TIME_PATTERN.match(clean)
        if not match:
            raise ValueError(
                "Некорректный формат времени. Используйте ЧЧ:ММ (например, 10:00 или 14:30)"
            )

        h1, m1, h2, m2 = match.groups()
        return f"{int(h1):02d}:{int(m1):02d}"

    def list_days(self) -> List[str]:
        """Return list of all available timetable dates sorted chronologically/alphabetically."""
        days_set = set()
        if os.path.exists(self.directory_path):
            for filename in os.listdir(self.directory_path):
                if filename.endswith(".json"):
                    days_set.add(filename[:-5])

        for date_key, staged_val in self._staged_days.items():
            if staged_val is None:
                days_set.discard(date_key)
            else:
                days_set.add(date_key)

        return sorted(days_set, key=self._sort_key_for_date)

    @staticmethod
    def _sort_key_for_date(date_str: str) -> Any:
        """Helper to sort dates in chronological order."""
        if len(date_str) == 8 and date_str.isdigit():
            day = int(date_str[:2])
            month = int(date_str[2:4])
            year = int(date_str[4:])
            return (year, month, day)
        return (9999, 12, 31, date_str)

    @staticmethod
    def _sort_event_key(event: Any) -> tuple:
        """Helper to sort events chronologically by start time, then by name."""
        if isinstance(event, dict):
            time_str = str(event.get("time", "")).strip()
            title_str = str(event.get("title", "")).strip()
        else:
            time_str = str(getattr(event, "time", "")).strip()
            title_str = str(getattr(event, "title", "")).strip()

        start_time_part = time_str.split("-")[0].strip()
        match = re.match(r"^(\d{1,2}):(\d{2})$", start_time_part)
        if match:
            time_val = (0, int(match.group(1)), int(match.group(2)))
        else:
            time_val = (1, time_str)
        return (time_val, title_str.lower(), title_str)

    def get_all_locations(self) -> List[str]:
        """Collect and return all unique locations across all timetable files and staged changes."""
        locations_set = set()
        for date_key in self.list_days():
            data = self.get_day_dict(date_key)
            if data and "events" in data:
                for event in data["events"]:
                    loc = event.get("location", "")
                    if loc and loc.strip():
                        locations_set.add(loc.strip())

        return sorted(locations_set)

    def get_day_dict(self, date: str) -> Optional[Dict[str, Any]]:
        """Load raw JSON dictionary for specified date from staged changes or disk."""
        clean_date = date.strip()
        if clean_date in self._staged_days:
            staged = self._staged_days[clean_date]
            if staged is not None and "events" in staged and isinstance(staged["events"], list):
                staged["events"].sort(key=self._sort_event_key)
            return copy.deepcopy(staged) if staged is not None else None

        file_path = os.path.join(self.directory_path, f"{clean_date}.json")
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            if "events" in data and isinstance(data["events"], list):
                data["events"].sort(key=self._sort_event_key)
            return data
        except Exception:
            return None

    def get_day_timetable(self, date: str) -> Optional[DayTimetable]:
        """Load DayTimetable for specified date."""
        data = self.get_day_dict(date)
        if not data:
            return None
        try:
            return DayTimetable.from_dict(data)
        except Exception:
            return None

    def save_day_dict(self, date: str, data: Dict[str, Any]) -> None:
        """Stage day dictionary in-memory without immediately writing to disk."""
        clean_date = date.strip()
        cloned = copy.deepcopy(data)
        if "events" in cloned and isinstance(cloned["events"], list):
            cloned["events"].sort(key=self._sort_event_key)
        self._staged_days[clean_date] = cloned
        self._has_pending_changes = True

    def save_to_disk(self) -> None:
        """Commit all staged day changes to JSON asset files on disk."""
        os.makedirs(self.directory_path, exist_ok=True)
        for date_key, staged_val in self._staged_days.items():
            file_path = os.path.join(self.directory_path, f"{date_key}.json")
            if staged_val is None:
                if os.path.exists(file_path):
                    os.remove(file_path)
            else:
                if "events" in staged_val and isinstance(staged_val["events"], list):
                    staged_val["events"].sort(key=self._sort_event_key)
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(staged_val, f, ensure_ascii=False, indent=2)
                    f.write("\n")
        self._staged_days.clear()
        self._has_pending_changes = False

    commit = save_to_disk

    def discard_changes(self) -> None:
        """Discard in-memory changes and revert to disk files."""
        self._staged_days.clear()
        self._has_pending_changes = False

    rollback = discard_changes

    def has_pending_changes(self) -> bool:
        """Return whether there are uncommitted timetable changes."""
        return self._has_pending_changes

    def create_day(self, date: str) -> str:
        """Create a new timetable entry for date if it doesn't already exist."""
        clean_date = self.validate_and_normalize_date(date)

        existing = self.get_day_dict(clean_date)
        if existing is not None:
            raise ValueError(f"Timetable for date '{clean_date}' already exists / Расписание на дату '{clean_date}' уже существует")

        data = {"date": clean_date, "events": []}
        self.save_day_dict(clean_date, data)
        return clean_date

    def delete_day(self, date: str) -> None:
        """Delete a timetable entry for the specified date."""
        clean_date = date.strip()
        existing = self.get_day_dict(clean_date)
        if existing is None:
            raise ValueError(f"Timetable for date '{clean_date}' not found / Расписание на дату '{clean_date}' не найдено")

        self._staged_days[clean_date] = None
        self._has_pending_changes = True

    def add_event(
        self,
        date: str,
        time: str,
        title: str,
        location: str,
        description: str = "",
        participants: Any = None,
        organizer: str = "",
        is_children_activity: Any = False,
    ) -> None:
        """Add an event to a date timetable, enforcing mandatory start time, title, and location."""
        event_dict = self._validate_and_build_event(
            time=time,
            title=title,
            location=location,
            description=description,
            participants=participants,
            organizer=organizer,
            is_children_activity=is_children_activity,
        )

        clean_date = date.strip()
        data = self.get_day_dict(clean_date)
        if data is None:
            raise ValueError(f"Timetable for date '{clean_date}' not found")

        data.setdefault("events", []).append(event_dict)
        self.save_day_dict(clean_date, data)

    def update_event(
        self,
        date: str,
        event_index: int,
        time: str,
        title: str,
        location: str,
        description: str = "",
        participants: Any = None,
        organizer: str = "",
        is_children_activity: Any = False,
    ) -> None:
        """Update an event by index for a given date."""
        event_dict = self._validate_and_build_event(
            time=time,
            title=title,
            location=location,
            description=description,
            participants=participants,
            organizer=organizer,
            is_children_activity=is_children_activity,
        )

        clean_date = date.strip()
        data = self.get_day_dict(clean_date)
        if data is None:
            raise ValueError(f"Timetable for date '{clean_date}' not found")

        events = data.get("events", [])
        if not (0 <= event_index < len(events)):
            raise IndexError("Event index out of range")

        events[event_index] = event_dict
        self.save_day_dict(clean_date, data)

    def delete_event(self, date: str, event_index: int) -> None:
        """Delete an event by index for a given date."""
        clean_date = date.strip()
        data = self.get_day_dict(clean_date)
        if data is None:
            raise ValueError(f"Timetable for date '{clean_date}' not found")

        events = data.get("events", [])
        if not (0 <= event_index < len(events)):
            raise IndexError("Event index out of range")

        events.pop(event_index)
        self.save_day_dict(clean_date, data)

    def toggle_event_children_activity(self, date: str, event_index: int) -> bool:
        """Toggle is_children_activity flag for an event by index."""
        clean_date = date.strip()
        data = self.get_day_dict(clean_date)
        if data is None:
            raise ValueError(f"Timetable for date '{clean_date}' not found")

        events = data.get("events", [])
        if not (0 <= event_index < len(events)):
            raise IndexError("Event index out of range")

        current = bool(events[event_index].get("is_children_activity", False))
        events[event_index]["is_children_activity"] = not current
        self.save_day_dict(clean_date, data)
        return events[event_index]["is_children_activity"]

    def set_event_children_activity(self, date: str, event_index: int, is_children: bool) -> None:
        """Set is_children_activity flag for an event by index."""
        clean_date = date.strip()
        data = self.get_day_dict(clean_date)
        if data is None:
            raise ValueError(f"Timetable for date '{clean_date}' not found")

        events = data.get("events", [])
        if not (0 <= event_index < len(events)):
            raise IndexError("Event index out of range")

        events[event_index]["is_children_activity"] = bool(is_children)
        self.save_day_dict(clean_date, data)

    def _validate_and_build_event(
        self,
        time: str,
        title: str,
        location: str,
        description: str = "",
        participants: Any = None,
        organizer: str = "",
        is_children_activity: Any = False,
    ) -> Dict[str, Any]:
        """Validate mandatory attributes (time, title, location) and construct event dictionary."""
        clean_time = self.validate_time(time)
        clean_title = (title or "").strip()
        clean_location = (location or "").strip()

        if not clean_title:
            raise ValueError("Field 'title' is mandatory and cannot be empty / Поле 'Название' обязательно для заполнения")
        if not clean_location:
            raise ValueError("Field 'location' is mandatory and cannot be empty / Поле 'Локация' обязательно для заполнения")

        clean_participants = self._parse_list_field(participants)
        clean_description = (description or "").strip()
        clean_organizer = (organizer or "").strip()

        if isinstance(is_children_activity, str):
            clean_children = is_children_activity.strip().lower() in ("1", "true", "yes", "on")
        else:
            clean_children = bool(is_children_activity)

        return {
            "time": clean_time,
            "title": clean_title,
            "description": clean_description,
            "participants": clean_participants,
            "organizer": clean_organizer,
            "location": clean_location,
            "is_children_activity": clean_children,
        }

    @staticmethod
    def _parse_list_field(value: Any) -> List[str]:
        """Convert string or list into list of clean non-empty strings."""
        if value is None:
            return []
        if isinstance(value, str):
            raw_items = [part.strip() for line in value.splitlines() for part in line.split(",")]
            return [item for item in raw_items if item]
        if isinstance(value, (list, tuple, set)):
            items = []
            for item in value:
                clean = str(item).strip()
                if clean:
                    items.append(clean)
            return items
        clean_str = str(value).strip()
        return [clean_str] if clean_str else []
