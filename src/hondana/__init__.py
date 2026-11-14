"""hondana — fold Japanese/CJK book metadata for matching, look up ISBNs."""
from .fold import fold, fold_steps, hira_to_kata, kata_to_hira, strip_reading_lines, to_shinjitai, width
from .isbn import find_isbns, hyphenate, is_valid, to_isbn10, to_isbn13
from .export import dumps, to_bibtex, to_csl, to_ris
from .lookup import Book, cached, lookup, lookup_many
from .dedupe import DuplicateGroup, DedupeResult, dedupe, dedupe_key

__version__ = "0.2.0"
__all__ = [
    "fold", "fold_steps", "kata_to_hira", "hira_to_kata", "to_shinjitai", "width", "strip_reading_lines",
    "is_valid", "to_isbn13", "to_isbn10", "find_isbns", "hyphenate",
    "Book", "lookup", "lookup_many", "cached",
    "dedupe", "dedupe_key", "DuplicateGroup", "DedupeResult",
    "to_bibtex", "to_ris", "to_csl", "dumps",
]
