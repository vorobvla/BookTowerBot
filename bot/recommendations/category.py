"""Recommendation category data model containing books."""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from bot.recommendations.book import Book


@dataclass
class RecommendationCategory:
    """Represents a category/compilation of recommended books."""

    name: str
    emoji: str = ""
    books: List[Book] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecommendationCategory":
        """Create RecommendationCategory instance from a dictionary."""
        name = str(data.get("rec", data.get("name", ""))).strip()
        emoji = str(data.get("emoji", "")).strip()
        raw_books = data.get("books") or []
        books = [Book.from_dict(item) for item in raw_books if isinstance(item, dict)]
        return cls(name=name, emoji=emoji, books=books)

    def format_markdown(self) -> str:
        """Format the category and its book list as Markdown."""
        header_emoji = self.emoji if self.emoji else "📚"
        lines = [
            f"{header_emoji} *Рекомендации: {self.name}*\n",
        ]

        if not self.books:
            lines.append("В данной категории пока нет книг.")
            return "\n".join(lines)

        for i, book in enumerate(self.books):
            lines.append(book.format_markdown())
            if i < len(self.books) - 1:
                lines.append("\n" + "─" * 22 + "\n")

        return "\n".join(lines)
