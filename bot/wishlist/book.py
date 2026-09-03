"""Book domain model for wishlist."""

from dataclasses import dataclass
from typing import Optional


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
        parts = [f"{prefix}*«{self.title}»*"]
        if self.authors:
            parts.append(f"— {self.authors}")
        details = []
        if self.publishing:
            details.append(f"Изд: {self.publishing}")
        if self.year:
            details.append(f"{self.year} г.")
        if self.isbn:
            details.append(f"ISBN: {self.isbn}")
        if details:
            parts.append(f"({', '.join(details)})")
        if self.user_notes:
            parts.append(f"\n   _Заметка: {self.user_notes}_")
        return " ".join(parts)
