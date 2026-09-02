"""Participant data model representing an event participant/exhibitor."""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Participant:
    """Represents an exhibitor or participant at the event."""

    name: str
    stand: str
    description: str = ""
    link: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Participant":
        """Create a Participant instance from a dictionary."""
        return cls(
            name=str(data.get("name", "")).strip(),
            stand=str(data.get("stand", "")).strip(),
            description=str(data.get("description", "")).strip(),
            link=str(data.get("link", "")).strip(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert Participant instance to dictionary following schema."""
        res: Dict[str, Any] = {
            "name": self.name,
            "stand": self.stand,
            "description": self.description,
            "link": self.link,
        }
        return res

    def format_button_label(self) -> str:
        """Format label for inline keyboard button with name and stand."""
        if self.stand:
            return f"📍 Стенд {self.stand} — {self.name}"
        return f"📍 {self.name}"

    def format_markdown(self) -> str:
        """Format full participant information as Markdown."""
        lines = [f"👥 *{self.name}*"]
        if self.stand:
            lines.append(f"📍 *Стенд:* {self.stand}")
        if self.description:
            lines.append(f"📝 {self.description}")
        if self.link:
            lines.append(f"🔗 *Ссылка:* {self.link}")
        return "\n".join(lines)
