"""Event data model for book festival timetable."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
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

        return cls(
            time=str(data.get("time", "")).strip(),
            title=str(data.get("title", "")).strip(),
            description=str(data.get("description", "")).strip(),
            participants=[str(p).strip() for p in participants if p],
            organizer=str(organizer).strip(),
            location=str(data.get("location", "")).strip(),
            is_children_activity=is_children_activity,
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
        }

    def format_markdown(self) -> str:
        """Format event details as Markdown."""
        lines = [f"⌚ *{self.time}* — *{self.title}*"]
        if self.description:
            lines.append(f"📝 {self.description}")
        if self.participants:
            lines.append(f"👥 *Участники:* {', '.join(self.participants)}")
        if self.organizer:
            lines.append(f"📖 *Организатор:* {self.organizer}")
        return "\n".join(lines)
