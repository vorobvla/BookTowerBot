"""Service for managing book recommendations data in the admin console."""

import copy
import json
import os
from typing import Any, Dict, List, Optional

from bot.content import RECS_PATH
from bot.recommendations.book import Book
from bot.recommendations.category import RecommendationCategory


class AdminRecsService:
    """Provides CRUD operations and validation for recommendations (recs.json)."""

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or RECS_PATH
        self._staged_data: Optional[Dict[str, Any]] = None
        self._has_pending_changes: bool = False

    def load_data(self) -> Dict[str, Any]:
        """Load recommendations data from staged in-memory cache or disk."""
        if self._staged_data is not None:
            return copy.deepcopy(self._staged_data)

        if not os.path.exists(self.file_path):
            return {"recs": []}

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"recs": []}
            if "recs" not in data or not isinstance(data["recs"], list):
                data["recs"] = []
            return data
        except Exception:
            return {"recs": []}

    def save_data(self, data: Dict[str, Any]) -> None:
        """Stage recommendations data in-memory without immediately writing to disk."""
        self._staged_data = copy.deepcopy(data)
        self._has_pending_changes = True

    def save_to_disk(self) -> None:
        """Commit staged in-memory data to the JSON asset file on disk."""
        data = self.load_data()
        os.makedirs(os.path.dirname(os.path.abspath(self.file_path)), exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        self._staged_data = None
        self._has_pending_changes = False

    commit = save_to_disk

    def discard_changes(self) -> None:
        """Discard in-memory changes and reload original data from disk."""
        self._staged_data = None
        self._has_pending_changes = False

    rollback = discard_changes

    def has_pending_changes(self) -> bool:
        """Return whether there are uncommitted changes."""
        return self._has_pending_changes

    def get_categories(self) -> List[RecommendationCategory]:
        """Return all recommendation categories as domain instances."""
        data = self.load_data()
        raw_recs = data.get("recs", [])
        return [RecommendationCategory.from_dict(item) for item in raw_recs if isinstance(item, dict)]

    def add_category(self, category_name: str, emoji: str = "") -> None:
        """Add a new empty recommendation category with optional emoji."""
        clean_name = category_name.strip()
        clean_emoji = (emoji or "").strip()
        if not clean_name:
            raise ValueError("Category name cannot be empty")

        data = self.load_data()
        for cat in data.get("recs", []):
            if cat.get("rec", "").strip().lower() == clean_name.lower():
                raise ValueError(f"Category '{clean_name}' already exists")

        new_cat: Dict[str, Any] = {
            "rec": clean_name,
            "books": [],
        }
        if clean_emoji:
            new_cat["emoji"] = clean_emoji

        data.setdefault("recs", []).append(new_cat)
        self.save_data(data)

    def rename_category(self, old_name: str, new_name: str, emoji: Optional[str] = None) -> None:
        """Rename an existing category and optionally update its emoji."""
        clean_old = old_name.strip()
        clean_new = new_name.strip()
        if not clean_new:
            raise ValueError("New category name cannot be empty")

        data = self.load_data()
        found = False
        for cat in data.get("recs", []):
            if cat.get("rec", "").strip().lower() == clean_old.lower():
                cat["rec"] = clean_new
                if emoji is not None:
                    clean_emoji = emoji.strip()
                    if clean_emoji:
                        cat["emoji"] = clean_emoji
                    elif "emoji" in cat:
                        del cat["emoji"]
                found = True
                break

        if not found:
            raise ValueError(f"Category '{old_name}' not found")

        self.save_data(data)

    def update_category(self, old_name: str, new_name: str, emoji: Optional[str] = None) -> None:
        """Update category name and emoji."""
        self.rename_category(old_name=old_name, new_name=new_name, emoji=emoji)

    def delete_category(self, category_name: str) -> None:
        """Delete a category and all its books."""
        clean_name = category_name.strip().lower()
        data = self.load_data()
        initial_len = len(data.get("recs", []))
        data["recs"] = [
            cat for cat in data.get("recs", [])
            if cat.get("rec", "").strip().lower() != clean_name
        ]
        if len(data["recs"]) == initial_len:
            raise ValueError(f"Category '{category_name}' not found")

        self.save_data(data)

    def add_book(
        self,
        category_name: str,
        title: str,
        sold_by: Any,
        description: str = "",
        authors: Any = None,
    ) -> None:
        """Add a new book to a specified category, validating mandatory title and soldBy."""
        book_dict = self._validate_and_build_book(
            title=title,
            sold_by=sold_by,
            description=description,
            authors=authors,
        )

        data = self.load_data()
        target_cat = None
        for cat in data.get("recs", []):
            if cat.get("rec", "").strip().lower() == category_name.strip().lower():
                target_cat = cat
                break

        if not target_cat:
            raise ValueError(f"Category '{category_name}' not found")

        target_cat.setdefault("books", []).append(book_dict)
        self.save_data(data)

    def update_book(
        self,
        category_name: str,
        book_index: int,
        title: str,
        sold_by: Any,
        description: str = "",
        authors: Any = None,
    ) -> None:
        """Update an existing book at index within a category."""
        book_dict = self._validate_and_build_book(
            title=title,
            sold_by=sold_by,
            description=description,
            authors=authors,
        )

        data = self.load_data()
        target_cat = None
        for cat in data.get("recs", []):
            if cat.get("rec", "").strip().lower() == category_name.strip().lower():
                target_cat = cat
                break

        if not target_cat:
            raise ValueError(f"Category '{category_name}' not found")

        books = target_cat.get("books", [])
        if not (0 <= book_index < len(books)):
            raise IndexError("Book index out of range")

        books[book_index] = book_dict
        self.save_data(data)

    def delete_book(self, category_name: str, book_index: int) -> None:
        """Delete a book by index within a category."""
        data = self.load_data()
        target_cat = None
        for cat in data.get("recs", []):
            if cat.get("rec", "").strip().lower() == category_name.strip().lower():
                target_cat = cat
                break

        if not target_cat:
            raise ValueError(f"Category '{category_name}' not found")

        books = target_cat.get("books", [])
        if not (0 <= book_index < len(books)):
            raise IndexError("Book index out of range")

        books.pop(book_index)
        self.save_data(data)

    def _validate_and_build_book(
        self,
        title: str,
        sold_by: Any,
        description: str = "",
        authors: Any = None,
    ) -> Dict[str, Any]:
        """Validate mandatory fields (title, sold by) and return standard dictionary."""
        clean_title = (title or "").strip()
        if not clean_title:
            raise ValueError("Field 'title' is mandatory and cannot be empty")

        # Parse and validate soldBy
        clean_sold_by = self._parse_list_field(sold_by)
        if not clean_sold_by:
            raise ValueError("Field 'sold by' is mandatory and must contain at least one vendor/booth")

        # Parse authors and description (optional)
        clean_authors = self._parse_list_field(authors)
        clean_description = (description or "").strip()

        return {
            "title": clean_title,
            "description": clean_description,
            "authors": clean_authors,
            "soldBy": clean_sold_by,
        }

    @staticmethod
    def _parse_list_field(value: Any) -> List[str]:
        """Convert string (comma or newline separated) or list to list of clean non-empty strings."""
        if value is None:
            return []
        if isinstance(value, str):
            # Split on commas and newlines
            raw_items = [part.strip() for line in value.splitlines() for part in line.split(",")]
            return [item for item in raw_items if item]
        if isinstance(value, (list, tuple, set)):
            items = []
            for item in value:
                clean = str(item).strip()
                if clean:
                    items.append(clean)
            return items
        clean_str = str(value).strip()
        return [clean_str] if clean_str else []
