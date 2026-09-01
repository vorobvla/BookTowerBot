"""Day timetable data model containing all events for a specific date."""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from bot.timetable.event import Event


@dataclass
class DayTimetable:
    """Represents full timetable for a single day."""

    date: str
    events: List[Event] = field(default_factory=list)

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

    def get_locations(self) -> List[str]:
        """Return list of distinct locations holding events on this day."""
        seen = set()
        locations = []
        for event in self.events:
            loc = event.location
            if loc and loc not in seen:
                seen.add(loc)
                locations.append(loc)
        return locations

    def get_events_for_location(self, location: str) -> List[Event]:
        """Return list of events scheduled at the specified location on this day."""
        target_loc = location.strip().lower()
        return [
            event
            for event in self.events
            if event.location.strip().lower() == target_loc
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
