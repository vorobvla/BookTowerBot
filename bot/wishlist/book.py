"""Book domain model for wishlist."""

from dataclasses import dataclass
from typing import Optional
from telegram.helpers import escape_markdown


@dataclass
class Book:
    """Book item stored in a user's wishlist."""

    title: str
    authors: Optional[str] = None
    publishing: Optional[str] = None
    isbn: Optional[str] = None
    year: Optional[int] = None
    user_notes: Optional[str] = None
    id: Optional[int] = None

    def __post_init__(self):
        if not self.title or not self.title.strip():
            raise ValueError("Title is required for a book")
        self.title = self.title.strip()
        if self.year is not None:
            try:
                self.year = int(self.year)
            except (ValueError, TypeError):
                self.year = None

    def format_entry(self, index: Optional[int] = None) -> str:
        """Format the book entry as a readable markdown string."""
        prefix = f"{index}. " if index is not None else "• "
        safe_title = escape_markdown(self.title, version=1)
        parts = [f"{prefix}*«{safe_title}»*"]
        if self.authors:
            safe_authors = escape_markdown(self.authors, version=1)
            parts.append(f"— {safe_authors}")
        details = []
        if self.publishing:
            safe_pub = escape_markdown(self.publishing, version=1)
            details.append(f"Изд: {safe_pub}")
        if self.year:
            details.append(f"{self.year} г.")
        if self.isbn:
            safe_isbn = escape_markdown(self.isbn, version=1)
            details.append(f"ISBN: {safe_isbn}")
        if details:
            parts.append(f"({', '.join(details)})")
        if self.user_notes:
            safe_notes = escape_markdown(self.user_notes, version=1)
            parts.append(f"\n   _Заметка: {safe_notes}_")
        return " ".join(parts)

    to_markdown = format_entry
