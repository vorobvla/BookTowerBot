"""Book data model for recommendations."""

from dataclasses import dataclass, field
from typing import Any, Dict, List
from telegram.helpers import escape_markdown


@dataclass
class Book:
    """Represents a recommended book."""

    title: str
    description: str = ""
    authors: List[str] = field(default_factory=list)
    sold_by: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], escape_markup: bool = False) -> "Book":
        """Create a Book instance from a dictionary."""
        authors = data.get("authors") or []
        if isinstance(authors, str):
            authors = [authors]

        sold_by = data.get("soldBy") or data.get("sold_by") or []
        if isinstance(sold_by, str):
            sold_by = [sold_by]

        raw_title = str(data.get("title", "")).strip()
        raw_desc = str(data.get("description", "")).strip()
        raw_authors = [str(a).strip() for a in authors if a]
        raw_sold_by = [str(s).strip() for s in sold_by if s]

        return cls(
            title=raw_title,
            description=raw_desc,
            authors=raw_authors,
            sold_by=raw_sold_by,
        )

    def format_markdown(self) -> str:
        """Format book information as Markdown."""
        safe_title = escape_markdown(self.title, version=1)
        lines = [f"📖 *{safe_title}*"]
        if self.description:
            safe_desc = escape_markdown(self.description, version=1)
            lines.append(f"📝 {safe_desc}")
        if self.authors:
            authors_label = "Автор" if len(self.authors) == 1 else "Авторы"
            safe_authors = ", ".join(escape_markdown(a, version=1) for a in self.authors)
            lines.append(f"✍️ *{authors_label}:* {safe_authors}")
        if self.sold_by:
            safe_sold_by = ", ".join(escape_markdown(s, version=1) for s in self.sold_by)
            lines.append(f"🏢 *Где купить:* {safe_sold_by}")
        return "\n".join(lines)

    to_markdown = format_markdown
