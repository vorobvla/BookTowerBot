"""ISBN lookup and barcode scanning utilities using isbnlib and zxing-cpp."""

import io
import logging
import os
import re
from typing import BinaryIO, Optional, Union
import isbnlib
from PIL import Image
import zxingcpp

from bot.wishlist.book import Book

logger = logging.getLogger(__name__)


def clean_isbn(raw: Optional[str]) -> Optional[str]:
    """Extract and validate clean ISBN (ISBN-10 or ISBN-13) using isbnlib."""
    if not raw:
        return None
    raw_str = str(raw).strip()

    # 1. Try direct canonical check
    canonical = isbnlib.canonical(raw_str)
    if canonical and (isbnlib.is_isbn10(canonical) or isbnlib.is_isbn13(canonical)):
        return canonical

    # 2. Extract potential ISBN substrings
    likes = isbnlib.get_isbnlike(raw_str)
    for candidate in likes:
        c = isbnlib.canonical(candidate)
        if c and (isbnlib.is_isbn10(c) or isbnlib.is_isbn13(c)):
            return c

    # 3. Fallback check for digit-cleaned strings
    cleaned = re.sub(r"[\s\-–—]", "", raw_str.upper())
    canonical_cleaned = isbnlib.canonical(cleaned)
    if canonical_cleaned and (isbnlib.is_isbn10(canonical_cleaned) or isbnlib.is_isbn13(canonical_cleaned)):
        return canonical_cleaned

    return None


def decode_barcode_from_image(image_source: Union[str, bytes, BinaryIO, Image.Image]) -> Optional[str]:
    """
    Read barcode from image source and extract valid ISBN/EAN using zxing-cpp and Pillow.
    Accepts a file path, bytes, file-like object, or PIL Image.
    """
    try:
        if isinstance(image_source, Image.Image):
            pil_image = image_source
        elif isinstance(image_source, (bytes, bytearray)):
            pil_image = Image.open(io.BytesIO(image_source))
        elif isinstance(image_source, str) and os.path.exists(image_source):
            pil_image = Image.open(image_source)
        elif hasattr(image_source, "read"):
            pil_image = Image.open(image_source)
        else:
            return None

        # Try reading all barcodes in the image
        results = zxingcpp.read_barcodes(pil_image)
        if not results:
            # Try single barcode read
            single = zxingcpp.read_barcode(pil_image)
            results = [single] if single else []

        for result in results:
            if not result or not result.text:
                continue
            cleaned = clean_isbn(result.text)
            if cleaned:
                return cleaned
            # If barcode text is numeric and 10 or 13 digits
            digits = re.sub(r"\D", "", result.text)
            if len(digits) in (10, 13):
                return digits

        return None
    except Exception as e:
        logger.error(f"Error decoding barcode from image: {e}", exc_info=True)
        return None


def _extract_year(raw_year: Optional[Union[str, int]]) -> Optional[int]:
    """Extract 4-digit publication year."""
    if not raw_year:
        return None
    match = re.search(r"\b(18\d\d|19\d\d|20\d\d)\b", str(raw_year))
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def lookup_book_by_isbn(isbn: str, service: Optional[str] = None) -> Optional[Book]:
    """
    Look up book details by ISBN using isbnlib metadata providers (openl, goob, wiki, default).
    Returns the single best Book instance or None if not found.
    """
    cleaned = clean_isbn(isbn)
    if not cleaned:
        return None

    services_to_try = [service] if service else ["openl", "goob", "wiki", "default"]
    meta = None

    for s in services_to_try:
        try:
            res = isbnlib.meta(cleaned, service=s)
            if res and isinstance(res, dict) and res.get("Title"):
                meta = res
                break
        except Exception as e:
            logger.debug(f"isbnlib.meta failed for service={s}: {e}")
            continue

    if not meta or not meta.get("Title"):
        return None

    title = str(meta.get("Title", "")).strip()
    if not title:
        return None

    raw_authors = meta.get("Authors", [])
    if isinstance(raw_authors, list):
        authors = ", ".join([str(a).strip() for a in raw_authors if str(a).strip()]) or None
    elif raw_authors:
        authors = str(raw_authors).strip() or None
    else:
        authors = None

    publisher = meta.get("Publisher")
    publishing = str(publisher).strip() if publisher else None

    year = _extract_year(meta.get("Year"))

    return Book(
        title=title,
        authors=authors,
        publishing=publishing,
        isbn=cleaned,
        year=year,
    )
