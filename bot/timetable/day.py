"""Day timetable data model containing all events for a specific date."""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from bot.timetable.event import Event


@dataclass
class DayTimetable:
    """Represents full timetable for a single day."""

    date: str
    events: List[Event] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Ensure events are sorted chronologically by time, then alphabetically by title."""
        if self.events and isinstance(self.events, list):
            self.events.sort(key=self._sort_event_key)

    @staticmethod
    def _sort_event_key(event: Event) -> tuple:
        """Helper to sort events chronologically by start time, then by name."""
        time_str = str(getattr(event, "time", "")).strip()
        title_str = str(getattr(event, "title", "")).strip()
        start_time_part = time_str.split("-")[0].strip()
        match = re.match(r"^(\d{1,2}):(\d{2})$", start_time_part)
        if match:
            time_val = (0, int(match.group(1)), int(match.group(2)))
        else:
            time_val = (1, time_str)
        return (time_val, title_str.lower(), title_str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DayTimetable":
        """Create DayTimetable instance from a dictionary."""
        date = str(data.get("date", "")).strip()
        raw_events = data.get("events") or []
        events = [Event.from_dict(item) for item in raw_events if isinstance(item, dict)]
        return cls(date=date, events=events)

    @classmethod
    def from_file(cls, file_path: str) -> "DayTimetable":
        """Load DayTimetable from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def get_locations(self, children_only: bool = False) -> List[str]:
        """Return list of distinct locations holding events on this day."""
        seen = set()
        locations = []
        for event in self.events:
            if children_only and not event.is_children_activity:
                continue
            loc = event.location
            if loc and loc not in seen:
                seen.add(loc)
                locations.append(loc)
        return locations

    def get_events_for_location(self, location: str, children_only: bool = False) -> List[Event]:
        """Return list of events scheduled at the specified location on this day."""
        target_loc = location.strip().lower()
        return [
            event
            for event in self.events
            if event.location.strip().lower() == target_loc
            and (not children_only or event.is_children_activity)
        ]

    def format_date_display(self) -> str:
        """Format the date string into a user-friendly display format (DD.MM.YYYY)."""
        raw = self.date.strip()
        if len(raw) == 8 and raw.isdigit():
            day = raw[:2]
            month = raw[2:4]
            year = raw[4:]
            return f"{day}.{month}.{year}"
        return raw
