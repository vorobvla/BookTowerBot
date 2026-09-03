"""Pytest configuration and global fixtures."""

import os
import tempfile
import pytest

# Ensure tests never write to real database by default
_TEST_TEMP_DIR = tempfile.TemporaryDirectory()
_TEST_DB_PATH = os.path.join(_TEST_TEMP_DIR.name, "test_wishlist.db")
os.environ["WISHLIST_DB_PATH"] = _TEST_DB_PATH
os.environ.setdefault("WISHLIST_SALT", "test_secret_salt")
