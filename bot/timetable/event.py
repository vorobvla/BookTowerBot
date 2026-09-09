"""Event data model for book festival timetable."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from telegram.helpers import escape_markdown


@dataclass
class Event:
    """Represents a single event/session in the timetable."""

    time: str
    title: str
    description: str = ""
    participants: List[str] = field(default_factory=list)
    organizer: str = ""
    location: str = ""
    is_children_activity: bool = False
    is_master_class: bool = False
    description_markup: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any], escape_markup: bool = False) -> "Event":
        """Create Event instance from a dictionary."""
        organizer = data.get("organizer") or ""
        participants = data.get("participants") or []
        if isinstance(participants, str):
            participants = [participants]

        raw_children = data.get("is_children_activity", False)
        if isinstance(raw_children, str):
            is_children_activity = raw_children.strip().lower() in ("1", "true", "yes", "on")
        else:
            is_children_activity = bool(raw_children)

        raw_master = data.get("is_master_class") if "is_master_class" in data else data.get("is_masterclass", False)
        if isinstance(raw_master, str):
            is_master_class = raw_master.strip().lower() in ("1", "true", "yes", "on")
        else:
            is_master_class = bool(raw_master)

        raw_markup = data.get("description_markup", False)
        if isinstance(raw_markup, str):
            description_markup = raw_markup.strip().lower() in ("1", "true", "yes", "on")
        else:
            description_markup = bool(raw_markup)

        raw_time = str(data.get("time", "")).strip()
        raw_title = str(data.get("title", "")).strip()
        raw_description = str(data.get("description", "")).strip()
        raw_organizer = str(organizer).strip()
        raw_location = str(data.get("location", "")).strip()
        raw_participants_list = [str(p).strip() for p in participants if p]

        return cls(
            time=raw_time,
            title=raw_title,
            description=raw_description,
            participants=raw_participants_list,
            organizer=raw_organizer,
            location=raw_location,
            is_children_activity=is_children_activity,
            is_master_class=is_master_class,
            description_markup=description_markup,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert Event instance to dictionary representation."""
        return {
            "time": self.time,
            "title": self.title,
            "description": self.description,
            "participants": self.participants,
            "organizer": self.organizer,
            "location": self.location,
            "is_children_activity": self.is_children_activity,
            "is_master_class": self.is_master_class,
            "description_markup": self.description_markup,
        }

    def format_markdown(self) -> str:
        """Format event details as Markdown."""
        safe_time = escape_markdown(self.time, version=1)
        safe_title = escape_markdown(self.title, version=1)
        lines = [f"⌚ *{safe_time}* — *{safe_title}*"]
        if self.description:
            if self.description_markup:
                desc = self.description
            else:
                desc = escape_markdown(self.description, version=1)
            lines.append(f"📝 {desc}")
        if self.participants:
            safe_parts = ", ".join(escape_markdown(p, version=1) for p in self.participants)
            lines.append(f"👥 *Участники:* {safe_parts}")
        if self.organizer:
            safe_org = escape_markdown(self.organizer, version=1)
            lines.append(f"📖 *Организатор:* {safe_org}")
        return "\n".join(lines)

    to_markdown = format_markdown
