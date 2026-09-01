"""Book data model for recommendations."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Book:
    """Represents a recommended book."""

    title: str
    description: str = ""
    authors: List[str] = field(default_factory=list)
    sold_by: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Book":
        """Create a Book instance from a dictionary."""
        authors = data.get("authors") or []
        if isinstance(authors, str):
            authors = [authors]

        sold_by = data.get("soldBy") or data.get("sold_by") or []
        if isinstance(sold_by, str):
            sold_by = [sold_by]

        return cls(
            title=str(data.get("title", "")).strip(),
            description=str(data.get("description", "")).strip(),
            authors=[str(a).strip() for a in authors if a],
            sold_by=[str(s).strip() for s in sold_by if s],
        )

    def format_markdown(self) -> str:
        """Format book information as Markdown."""
        lines = [f"📖 *{self.title}*"]
        if self.description:
            lines.append(f"📝 {self.description}")
        if self.authors:
            authors_label = "Автор" if len(self.authors) == 1 else "Авторы"
            lines.append(f"✍️ *{authors_label}:* {', '.join(self.authors)}")
        if self.sold_by:
            lines.append(f"🏢 *Где купить:* {', '.join(self.sold_by)}")
        return "\n".join(lines)
