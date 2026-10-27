"""hondana — fold Japanese/CJK book metadata for matching, look up ISBNs."""
from .fold import fold, fold_steps, hira_to_kata, kata_to_hira, strip_reading_lines, to_shinjitai, width
from .isbn import find_isbns, hyphenate, is_valid, to_isbn10, to_isbn13
from .lookup import Book, cached, lookup

__version__ = "0.1.0"
__all__ = [
    "fold", "fold_steps", "kata_to_hira", "hira_to_kata", "to_shinjitai", "width", "strip_reading_lines",
    "is_valid", "to_isbn13", "to_isbn10", "find_isbns", "hyphenate",
    "Book", "lookup", "cached",
]
