"""Wishlist database and service implementation."""

import hashlib
import os
import sqlite3
from pathlib import Path
from typing import List, Optional, Union
from dotenv import load_dotenv

from bot.wishlist.book import Book

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def get_user_id(telegram_id: Union[int, str]) -> str:
    """Generate anonymized user_id by hashing telegram_id with a secret salt from .env.

    The original telegram_id is never stored in the database.
    """
    salt = os.getenv("WISHLIST_SALT")
    if salt is None:
        raise ValueError("Salt must be provided for user_id hashing. Set WISHLIST_SALT in .env.")
    raw = f"{salt}:{telegram_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class WishlistService:
    """Service managing user wishlists stored in SQLite database."""

    def __init__(self, db_path: Optional[str] = None, salt: Optional[str] = None):
        if db_path is None:
            env_db = os.getenv("WISHLIST_DB_PATH", "assets/db/wishlist.db")
            if not os.path.isabs(env_db):
                self.db_path = str((PROJECT_ROOT / env_db).resolve())
            else:
                self.db_path = env_db
        else:
            self.db_path = db_path

        self.salt = salt
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a connection to the SQLite database with directory creation."""
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema with users and wishlist_books tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            # Users table: stores only user_id (hashed) and no other attributes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY
                );
            """)
            # Wishlist books table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wishlist_books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    authors TEXT,
                    publishing TEXT,
                    isbn TEXT,
                    year INTEGER,
                    user_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                );
            """)
            conn.commit()

    def get_or_create_user(self, user_id: str) -> str:
        """Ensure user_id exists in users table."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?);", (user_id,))
            conn.commit()
        return user_id

    def add_book(
        self,
        user_id: str,
        title: Optional[Union[str, Book]] = None,
        authors: Optional[str] = None,
        publishing: Optional[str] = None,
        isbn: Optional[str] = None,
        year: Optional[int] = None,
        user_notes: Optional[str] = None,
        *,
        book: Optional[Book] = None,
    ) -> Book:
        """Add a book to the user's wishlist."""
        if book is not None:
            target_book = book
        elif isinstance(title, Book):
            target_book = title
        elif title is not None:
            target_book = Book(
                title=str(title),
                authors=authors,
                publishing=publishing,
                isbn=isbn,
                year=year,
                user_notes=user_notes,
            )
        else:
            raise ValueError("title or book must be provided")

        self.get_or_create_user(user_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO wishlist_books (user_id, title, authors, publishing, isbn, year, user_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (user_id, target_book.title, target_book.authors, target_book.publishing, target_book.isbn, target_book.year, target_book.user_notes))
            target_book.id = cursor.lastrowid
            conn.commit()
        return target_book

    def get_wishlist(self, user_id: str) -> List[Book]:
        """Retrieve all books from user's wishlist ordered by creation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, authors, publishing, isbn, year, user_notes
                FROM wishlist_books
                WHERE user_id = ?
                ORDER BY id ASC;
            """, (user_id,))
            rows = cursor.fetchall()
            return [
                Book(
                    id=row["id"],
                    title=row["title"],
                    authors=row["authors"],
                    publishing=row["publishing"],
                    isbn=row["isbn"],
                    year=row["year"],
                    user_notes=row["user_notes"],
                )
                for row in rows
            ]

    def get_book(self, user_id: str, book_id: int) -> Optional[Book]:
        """Retrieve a single book from user's wishlist by id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, authors, publishing, isbn, year, user_notes
                FROM wishlist_books
                WHERE id = ? AND user_id = ?;
            """, (book_id, user_id))
            row = cursor.fetchone()
            if not row:
                return None
            return Book(
                id=row["id"],
                title=row["title"],
                authors=row["authors"],
                publishing=row["publishing"],
                isbn=row["isbn"],
                year=row["year"],
                user_notes=row["user_notes"],
            )

    def update_book_attribute(
        self, user_id: str, book_id: int, attribute: str, value: Optional[Union[str, int]]
    ) -> Optional[Book]:
        """Update a specific attribute of a book."""
        allowed_attributes = {"title", "authors", "publishing", "isbn", "year", "user_notes"}
        if attribute not in allowed_attributes:
            raise ValueError(f"Invalid attribute: {attribute}. Must be one of {allowed_attributes}")

        if attribute == "title":
            if not value or not str(value).strip():
                raise ValueError("Title cannot be empty")
            value = str(value).strip()
        elif attribute == "year":
            if value is not None and str(value).strip() != "":
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    raise ValueError("Year must be an integer")
            else:
                value = None
        elif isinstance(value, str):
            val_clean = value.strip()
            value = val_clean if val_clean else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE wishlist_books
                SET {attribute} = ?
                WHERE id = ? AND user_id = ?;
            """, (value, book_id, user_id))
            conn.commit()
            if cursor.rowcount == 0:
                return None

        return self.get_book(user_id, book_id)

    def update_book(self, user_id: str, book: Book) -> Optional[Book]:
        """Update all fields of an existing book."""
        if book.id is None:
            raise ValueError("Book ID must be set to update")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE wishlist_books
                SET title = ?, authors = ?, publishing = ?, isbn = ?, year = ?, user_notes = ?
                WHERE id = ? AND user_id = ?;
            """, (book.title, book.authors, book.publishing, book.isbn, book.year, book.user_notes, book.id, user_id))
            conn.commit()
            if cursor.rowcount == 0:
                return None
        return self.get_book(user_id, book.id)

    def format_wishlist_text(self, user_id: str) -> str:
        """Format the user's wishlist as a readable message."""
        books = self.get_wishlist(user_id)
        if not books:
            return (
                "📭 *Ваш список покупок пока пуст.*\n\n"
                "Нажмите «Добавить книгу» (или введите /addbook), чтобы добавить книгу в список."
            )

        lines = ["📋 *Ваш список покупок:*\n"]
        for idx, b in enumerate(books, start=1):
            lines.append(b.format_entry(index=idx))
        return "\n".join(lines)

    def delete_book(self, user_id: str, book_id: int) -> bool:
        """Delete a book from user's wishlist by id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM wishlist_books
                WHERE id = ? AND user_id = ?;
            """, (book_id, user_id))
            conn.commit()
            return cursor.rowcount > 0

    def clear_wishlist(self, user_id: str) -> int:
        """Remove all books from user's wishlist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM wishlist_books
                WHERE user_id = ?;
            """, (user_id,))
            conn.commit()
            return cursor.rowcount
