"""Participant data model representing an event participant/exhibitor."""

from dataclasses import dataclass
from typing import Any, Dict
from telegram.helpers import escape_markdown


@dataclass
class Participant:
    """Represents an exhibitor or participant at the event."""

    name: str
    stand: str
    description: str = ""
    link: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any], escape_markup: bool = False) -> "Participant":
        """Create a Participant instance from a dictionary."""
        raw_name = str(data.get("name", "")).strip()
        raw_stand = str(data.get("stand", "")).strip()
        raw_desc = str(data.get("description", "")).strip()
        raw_link = str(data.get("link", "")).strip()

        return cls(
            name=raw_name,
            stand=raw_stand,
            description=raw_desc,
            link=raw_link,
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
        safe_name = escape_markdown(self.name, version=1)
        lines = [f"👥 *{safe_name}*"]
        if self.stand:
            safe_stand = escape_markdown(self.stand, version=1)
            lines.append(f"📍 *Стенд:* {safe_stand}")
        if self.description:
            safe_desc = escape_markdown(self.description, version=1)
            lines.append(f"📝 {safe_desc}")
        if self.link:
            safe_link = escape_markdown(self.link, version=1)
            lines.append(f"🔗 *Ссылка:* {safe_link}")
        return "\n".join(lines)

    to_markdown = format_markdown
