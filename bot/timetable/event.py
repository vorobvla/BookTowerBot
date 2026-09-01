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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create Event instance from a dictionary."""
        organizer = data.get("organizer") or data.get("organizer") or ""
        participants = data.get("participants") or []
        if isinstance(participants, str):
            participants = [participants]

        return cls(
            time=str(data.get("time", "")).strip(),
            title=str(data.get("title", "")).strip(),
            description=str(data.get("description", "")).strip(),
            participants=[str(p).strip() for p in participants if p],
            organizer=str(organizer).strip(),
            location=str(data.get("location", "")).strip(),
        )

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
